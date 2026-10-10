"""Per-photo edits (rating, label, keywords and a non-destructive develop recipe) and their XMP sidecars.

The edits live in Daguerre's own database (``photo_edits``). Photos are never modified. When the owner turns on
"Write .xmp sidecars" (Settings, off by default) Daguerre also keeps ``<photo name>.xmp`` next to each edited photo,
in the standard form RAW developers use (see ``xmp.py``). Reading sidecars (and the XMP embedded in JPEG/TIFF/PNG/
WebP) is always on: a scan picks up ratings, labels, keywords and develop settings from them.

Only two kinds of files outside ``data/`` are ever written, both only with the setting on: the ``.xmp`` sidecar of
an edited photo, and nothing else. A sidecar that Daguerre did not write is backed up under ``data/xmp-backups``
before its first modification and is merged, never replaced.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import shutil
import sqlite3
import threading
from pathlib import Path
from typing import Any, Callable

from . import db as dbmod
from . import xmp as xmplib
from .hoard_link.atomic import write_bytes_atomic

log = logging.getLogger(__name__)

SETTING_KEY = "xmp_sidecars"
EDIT_FIELDS = ("recipe", "rating", "label", "keywords")
RECIPE_NOTE = (
    "A recipe is stored here and, with 'Write .xmp sidecars' on, in the photo's .xmp for RAW developers. "
    "Daguerre itself renders only the exposure (craft_develop_photo); the photo file is never changed."
)
BATCH = 400


def _utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(text: str | None, default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except ValueError:
        return default


class EditsMixin:
    """Mixed into ``Library``: expects ``self.conn``, ``self.settings`` and ``self._resolve_photo``."""

    # ------------------------------------------------------------------ #
    # Setting
    # ------------------------------------------------------------------ #
    def xmp_sidecars_enabled(self) -> bool:
        return dbmod.get_setting(self.conn, SETTING_KEY, "0") == "1"

    def set_xmp_sidecars(self, enabled: bool) -> None:
        dbmod.set_setting(self.conn, SETTING_KEY, "1" if enabled else "0")

    # ------------------------------------------------------------------ #
    # Rows
    # ------------------------------------------------------------------ #
    def _load_edits(self, photo_id: str) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM photo_edits WHERE photo_id = ?", (photo_id,)).fetchone()
        if not row:
            return {"exists": False, "recipe": {}, "rating": None, "label": None, "keywords": None, "imported": None,
                    "source": None, "sidecar_path": None, "sidecar_mtime_ns": None, "sidecar_size": None,
                    "sidecar_owner": None, "embedded_hash": None}
        d = dict(row)
        d["exists"] = True
        d["recipe"] = _loads(d.get("recipe"), {})
        d["keywords"] = _loads(d.get("keywords"), None)
        d["imported"] = _loads(d.get("imported"), None)
        return d

    def _upsert_edits(self, photo_id: str, **cols: Any) -> None:
        cols["updated_at"] = _utc_stamp()
        names = list(cols)
        marks = ",".join("?" * len(names))
        updates = ",".join(f"{n}=excluded.{n}" for n in names)
        self.conn.execute(
            f"INSERT INTO photo_edits(photo_id,{','.join(names)}) VALUES (?,{marks}) "
            f"ON CONFLICT(photo_id) DO UPDATE SET {updates}",
            (photo_id, *cols.values()),
        )

    def _photo_for_edits(self, photo_id: str) -> sqlite3.Row:
        from .library import ValidationError

        row = self._resolve_photo(photo_id, None)
        if row["video_id"]:
            raise ValidationError("key frames of videos have no edits or sidecars: use the photo files themselves")
        return row

    @staticmethod
    def _signature(side: Path) -> tuple[str, int, int]:
        st = side.stat()
        return str(side), st.st_mtime_ns, st.st_size

    def _view(self, photo: sqlite3.Row, e: dict[str, Any]) -> dict[str, Any]:
        side = xmplib.find_sidecar(Path(photo["path"]))
        sidecar: dict[str, Any] = {"path": str(side or xmplib.target_sidecar(Path(photo["path"]))), "exists": bool(side)}
        if side:
            try:
                recorded = (e["sidecar_path"], e["sidecar_mtime_ns"], e["sidecar_size"])
                sidecar["changed_on_disk"] = self._signature(side) != recorded
            except OSError:
                sidecar["exists"] = False
            if e["sidecar_owner"]:
                sidecar["written_by"] = e["sidecar_owner"]
        out: dict[str, Any] = {
            "photo_id": photo["id"],
            "rating": e["rating"],
            "label": e["label"],
            "keywords": e["keywords"],
            "recipe": e["recipe"],
            "source": e["source"],
            "sidecar": sidecar,
            "write_sidecars": self.xmp_sidecars_enabled(),
        }
        if e["imported"]:
            out["imported_not_applied"] = e["imported"]
        return out

    def edits_summary(self, photo: sqlite3.Row) -> dict[str, Any] | None:
        """For ``describe``: the edits of a photo, or None when it has none and no sidecar."""
        e = self._load_edits(photo["id"])
        has_data = e["exists"] and any(e[k] for k in ("rating", "label", "keywords", "recipe", "imported"))
        if not has_data and not xmplib.find_sidecar(Path(photo["path"])):
            return None
        return self._view(photo, e)

    # ------------------------------------------------------------------ #
    # Public operations
    # ------------------------------------------------------------------ #
    def get_edits(self, photo_id: str) -> dict[str, Any]:
        photo = self._photo_for_edits(photo_id)
        with self._edits_lock:
            self._refresh_from_sidecar(photo)
            view = self._view(photo, self._load_edits(photo["id"]))
        view["note"] = RECIPE_NOTE
        return view

    def set_edits(self, photo_id: str, patch: dict[str, Any], write: bool = True) -> dict[str, Any]:
        """Apply the given fields (``recipe``, ``rating``, ``label``, ``keywords``); fields not in ``patch`` stay.

        ``recipe`` is merged setting by setting (a value of None clears that setting); ``rating`` is -1 (rejected)
        or 0-5 (None clears), ``label`` a short text ("" or None clears), ``keywords`` a list ([] or None clears).
        When "Write .xmp sidecars" is on, the sidecar is updated too."""
        from .library import ValidationError

        if not isinstance(patch, dict):
            raise ValidationError("give at least one of: " + ", ".join(EDIT_FIELDS))
        unknown = sorted(set(patch) - set(EDIT_FIELDS))
        if unknown:
            raise ValidationError(f"unknown field(s): {', '.join(unknown)}. Accepted: {', '.join(EDIT_FIELDS)}")
        if not patch:
            raise ValidationError("give at least one of: " + ", ".join(EDIT_FIELDS))
        photo = self._photo_for_edits(photo_id)
        try:
            clean = self._validate_patch(patch)
        except xmplib.XmpError as exc:
            raise ValidationError(str(exc)) from None
        with self._edits_lock:
            self._refresh_from_sidecar(photo)
            cur = self._load_edits(photo["id"])
            cols: dict[str, Any] = {}
            cleared: list[str] = []
            recipe = cur["recipe"]
            if "recipe" in clean:
                recipe, cleared = xmplib.merge_recipe(cur["recipe"], clean["recipe"])
                cols["recipe"] = _json(recipe)
            for key in ("rating", "label"):
                if key in clean:
                    cols[key] = clean[key]
            if "keywords" in clean:
                cols["keywords"] = _json(clean["keywords"]) if clean["keywords"] else None
            if not cur["source"]:
                cols["source"] = "daguerre"
            self._upsert_edits(photo["id"], **cols)
            self.conn.commit()
            result: dict[str, Any] = {}
            if write:
                result = self._write_after_edit(photo, clean, cleared)
            view = self._view(photo, self._load_edits(photo["id"]))
        view["sidecar_write"] = result or {"written": False, "reason": "not requested"}
        return view

    def read_sidecar(self, photo_id: str) -> dict[str, Any]:
        """Re-read the photo's sidecar (or its embedded XMP) now and merge it into the edits."""
        from .library import ValidationError

        photo = self._photo_for_edits(photo_id)
        with self._edits_lock:
            side = xmplib.find_sidecar(Path(photo["path"]))
            if side:
                try:
                    self._import_sidecar(photo, side)
                except (xmplib.XmpError, OSError) as exc:
                    raise ValidationError(f"cannot read {side}: {exc}") from None
                found = "sidecar"
            else:
                self._import_embedded(photo)
                found = "embedded" if self._load_edits(photo["id"])["source"] == "embedded" else None
            self.conn.commit()
            view = self._view(photo, self._load_edits(photo["id"]))
        view["read"] = found or "nothing: this photo has no sidecar and no embedded XMP with develop data"
        return view

    def write_sidecar(self, photo_id: str) -> dict[str, Any]:
        """Write (or merge into) the photo's sidecar from its stored edits. Needs 'Write .xmp sidecars' on."""
        from .library import ValidationError

        photo = self._photo_for_edits(photo_id)
        with self._edits_lock:
            self._refresh_from_sidecar(photo)
            stored = self._load_edits(photo["id"])
            if not (stored["recipe"] or stored["label"] or stored["keywords"] or stored["rating"] is not None):
                raise ValidationError("nothing to write yet: set a rating, label, keywords or recipe first (photos_set_edits)")
            outcome = self._write_sidecar_file(photo, SidecarArgs.from_stored(self._load_edits(photo["id"])), strict=True)
            view = self._view(photo, self._load_edits(photo["id"]))
        view["sidecar_write"] = outcome
        return view

    # ------------------------------------------------------------------ #
    # Internals: validation, writing
    # ------------------------------------------------------------------ #
    def _validate_patch(self, patch: dict[str, Any]) -> dict[str, Any]:
        clean: dict[str, Any] = {}
        if "recipe" in patch:
            clean["recipe"] = xmplib.validate_recipe_patch(patch["recipe"])
        if "rating" in patch:
            value = patch["rating"]
            if value is None:
                clean["rating"] = None
            else:
                if isinstance(value, bool):
                    raise xmplib.XmpError("rating must be -1 (rejected) or 0 to 5 stars")
                try:
                    rating = int(value)
                except (TypeError, ValueError):
                    raise xmplib.XmpError("rating must be -1 (rejected) or 0 to 5 stars") from None
                if rating != float(value) or not -1 <= rating <= 5:
                    raise xmplib.XmpError(f"rating must be -1 (rejected) or 0 to 5 stars, got {value!r}")
                clean["rating"] = rating
        if "label" in patch:
            value = patch["label"]
            if value is None or (isinstance(value, str) and not value.strip()):
                clean["label"] = None
            elif isinstance(value, str) and len(value.strip()) <= 64:
                clean["label"] = " ".join(value.split())
            else:
                raise xmplib.XmpError("label must be a short text of at most 64 characters (for example 'Red')")
        if "keywords" in patch:
            value = patch["keywords"]
            if value is None:
                clean["keywords"] = []
            elif isinstance(value, list) and all(isinstance(k, str) for k in value):
                clean["keywords"] = xmplib.clean_keywords(value)
            else:
                raise xmplib.XmpError("keywords must be a list of words, for example [\"trip\", \"family\"]")
        return clean

    def _write_after_edit(self, photo: sqlite3.Row, clean: dict[str, Any], cleared: list[str]) -> dict[str, Any]:
        if not self.xmp_sidecars_enabled():
            return {"written": False, "reason": "'Write .xmp sidecars' is off (Settings); the edits are saved in Daguerre only"}
        args = SidecarArgs.from_stored(self._load_edits(photo["id"]))
        args.cleared = cleared
        # clearing in Daguerre writes the neutral value, so the sidecar does not keep a stale rating/label/keywords
        if "rating" in clean and clean["rating"] is None:
            args.rating = 0
        if "label" in clean and clean["label"] is None:
            args.label = ""
        if "keywords" in clean and not clean["keywords"]:
            args.keywords = []
        return self._write_sidecar_file(photo, args, strict=False)

    def _write_sidecar_file(self, photo: sqlite3.Row, args: "SidecarArgs", strict: bool) -> dict[str, Any]:
        from .library import ValidationError

        if not self.xmp_sidecars_enabled():
            msg = "'Write .xmp sidecars' is off. The owner can turn it on in Daguerre Settings; it is off by default."
            if strict:
                raise ValidationError(msg)
            return {"written": False, "reason": msg}
        photo_path = Path(photo["path"])
        if not photo_path.is_file():
            if strict:
                raise ValidationError(f"the photo file is not reachable right now: {photo_path}")
            return {"written": False, "error": f"the photo file is not reachable right now: {photo_path}"}
        side = xmplib.target_sidecar(photo_path)
        existing: bytes | None = None
        backup: str | None = None
        try:
            if side.is_file():
                if side.stat().st_size > xmplib.MAX_XMP_BYTES:
                    raise xmplib.XmpError("the existing sidecar is larger than 2 MB")
                existing = side.read_bytes()
                info = xmplib.read_xmp(existing)  # raises XmpError for anything that is not XMP
                if not info.written_by_daguerre:
                    backup = self._backup_foreign(photo["id"], side)
            data = xmplib.merge_sidecar(existing, xmplib.SidecarEdits(
                recipe=args.recipe, cleared=args.cleared, rating=args.rating, label=args.label, keywords=args.keywords))
            write_bytes_atomic(side, data)
            sig = self._signature(side)
        except xmplib.XmpError as exc:
            msg = f"the existing sidecar {side} is not usable XMP ({exc}); Daguerre will not overwrite it. Fix or move it, then retry"
            if strict:
                raise ValidationError(msg) from None
            return {"written": False, "error": msg}
        except OSError as exc:
            msg = f"cannot write {side}: {exc}"
            if strict:
                raise ValidationError(msg) from None
            return {"written": False, "error": msg}
        self._upsert_edits(photo["id"], sidecar_path=sig[0], sidecar_mtime_ns=sig[1], sidecar_size=sig[2],
                           sidecar_owner="daguerre")
        self.conn.commit()
        out = {"written": True, "path": str(side), "created": existing is None, "merged": existing is not None,
               "bytes": len(data)}
        if backup:
            out["backup_of_original"] = backup
        return out

    def _backup_foreign(self, photo_id: str, side: Path) -> str:
        folder = self.settings.data_dir / "xmp-backups"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{photo_id}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.xmp"
        shutil.copy2(side, target)
        return str(target)

    # ------------------------------------------------------------------ #
    # Internals: reading
    # ------------------------------------------------------------------ #
    def _refresh_from_sidecar(self, photo: sqlite3.Row) -> None:
        """Before an edit: if the sidecar changed on disk since Daguerre last saw it, take its values first."""
        side = xmplib.find_sidecar(Path(photo["path"]))
        if not side:
            return
        e = self._load_edits(photo["id"])
        try:
            if self._signature(side) != (e["sidecar_path"], e["sidecar_mtime_ns"], e["sidecar_size"]):
                self._import_sidecar(photo, side)
        except (xmplib.XmpError, OSError) as exc:
            log.warning("sidecar %s not read: %s", side, exc)
        finally:
            self.conn.commit()

    def _import_sidecar(self, photo: sqlite3.Row, side: Path) -> None:
        """Merge a sidecar into the stored edits. The sidecar's rating/label/keywords win; its develop settings
        overlay the stored recipe. The file's signature is recorded even when it cannot be read, so a broken file
        is not parsed again until it changes."""
        pid = photo["id"]
        sig = self._signature(side)
        try:
            if sig[2] > xmplib.MAX_XMP_BYTES:
                raise xmplib.XmpError("the sidecar is larger than 2 MB")
            info = xmplib.read_xmp(side.read_bytes())
        except (xmplib.XmpError, OSError):
            self._upsert_edits(pid, sidecar_path=sig[0], sidecar_mtime_ns=sig[1], sidecar_size=sig[2],
                               sidecar_owner="invalid")
            raise
        cur = self._load_edits(pid)
        base = dict(info.daguerre_recipe or {})
        mapped, unmapped = xmplib.crs_to_recipe(info.crs, photo["orientation"], info.orientation)
        base.update(mapped)
        cols: dict[str, Any] = {
            "recipe": _json({**cur["recipe"], **base}),
            "source": "sidecar",
            "sidecar_path": sig[0], "sidecar_mtime_ns": sig[1], "sidecar_size": sig[2],
            "sidecar_owner": "daguerre" if info.written_by_daguerre else "foreign",
            "imported": _json({"source": "sidecar", "crs": xmplib.limit_imported(unmapped)}) if unmapped else None,
        }
        if info.rating is not None:
            cols["rating"] = info.rating
        if info.label is not None:
            cols["label"] = info.label
        if info.keywords is not None:
            cols["keywords"] = _json(info.keywords)
        self._upsert_edits(pid, **cols)

    def _import_embedded(self, photo: sqlite3.Row) -> None:
        """First sight of a file with no sidecar: take rating, label and keywords from the XMP embedded in it.
        Develop settings embedded in a finished JPEG/TIFF are already baked into its pixels, so they are only
        listed as "imported, not applied" and never become a recipe."""
        pid = photo["id"]
        cols: dict[str, Any] = {"embedded_hash": photo["content_hash"]}
        data = xmplib.extract_embedded(Path(photo["path"]))
        info = None
        if data:
            try:
                info = xmplib.read_xmp(data)
            except xmplib.XmpError:
                info = None
        if info:
            cur = self._load_edits(pid)
            if cur["rating"] is None and info.rating is not None:
                cols["rating"] = info.rating
            if cur["label"] is None and info.label is not None:
                cols["label"] = info.label
            if cur["keywords"] is None and info.keywords is not None:
                cols["keywords"] = _json(info.keywords)
            extra = {k: v for k, v in info.crs.items() if k not in xmplib._STRUCTURAL_CRS}
            if extra and not cur["imported"]:
                cols["imported"] = _json({"source": "embedded", "crs": xmplib.limit_imported(extra)})
            if len(cols) > 1 and not cur["source"]:
                cols["source"] = "embedded"
        self._upsert_edits(pid, **cols)

    def _sync_sidecars(self, plan: list[tuple[dict, Path]], stats: dict, record_error: Callable[[Path, Any], None]) -> None:
        """Scan step: for every photo seen, read a new or changed sidecar, and read embedded XMP the first time a
        file (with this content) is seen. Cheap when nothing changed: one stat per photo and no file reads."""
        c = self.conn
        stats.setdefault("sidecars_read", 0)
        stats.setdefault("embedded_read", 0)
        paths = [str(p) for _, p in plan]
        for start in range(0, len(paths), BATCH):
            chunk = paths[start: start + BATCH]
            marks = ",".join("?" * len(chunk))
            rows = c.execute(
                f"SELECT p.*, e.sidecar_path AS e_path, e.sidecar_mtime_ns AS e_mtime, e.sidecar_size AS e_size, "
                f"e.embedded_hash AS e_embedded FROM photos p LEFT JOIN photo_edits e ON e.photo_id = p.id "
                f"WHERE p.missing = 0 AND p.video_id IS NULL AND p.path IN ({marks})", chunk,
            ).fetchall()
            for row in rows:
                with self._edits_lock:
                    side = xmplib.find_sidecar(Path(row["path"]))
                    if side:
                        try:
                            if self._signature(side) != (row["e_path"], row["e_mtime"], row["e_size"]):
                                self._import_sidecar(row, side)
                                stats["sidecars_read"] += 1
                        except (xmplib.XmpError, OSError) as exc:
                            record_error(side, f"sidecar not read: {exc}")
                    else:
                        if row["e_path"] is not None:  # the sidecar disappeared: keep the edits, forget the file
                            self._upsert_edits(row["id"], sidecar_path=None, sidecar_mtime_ns=None,
                                               sidecar_size=None, sidecar_owner=None)
                        if row["e_embedded"] != row["content_hash"]:
                            self._import_embedded(row)
                            stats["embedded_read"] += 1
            c.commit()


class SidecarArgs:
    """What goes into a sidecar write: the stored recipe and the non-empty rating, label and keywords."""

    def __init__(self, recipe: dict[str, Any], rating: int | None, label: str | None, keywords: list[str] | None):
        self.recipe = recipe
        self.rating = rating
        self.label = label
        self.keywords = keywords
        self.cleared: list[str] = []

    @classmethod
    def from_stored(cls, e: dict[str, Any]) -> "SidecarArgs":
        return cls(dict(e["recipe"]), e["rating"], e["label"], e["keywords"])

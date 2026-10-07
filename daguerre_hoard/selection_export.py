"""An ordered, portable preview collection with original identities intact."""
from __future__ import annotations

import base64
import hashlib
import html
import io
import json
from pathlib import Path
from PIL import Image

from .contact_sheet import ContactSheetItem, MAX_ITEMS, render_contact_sheet
from .hoard_link.atomic import write_bytes_atomic, write_json_atomic, write_text_atomic
from .hashing import content_hash
from .scanning import stat_signature
from .thumbnails import thumb_path


def _gallery(title: str, entries: list[dict], images: list[bytes]) -> str:
    figures = []
    for entry, image in zip(entries, images):
        label = html.escape(Path(entry["path"]).name)
        caption = html.escape(entry.get("caption") or "")
        uri = "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii")
        figures.append(f'<figure><img src="{uri}" alt="{label}" loading="lazy">'
                       f'<figcaption><span class="number">{entry["n"]:02}</span><div>'
                       f'<strong>{label}</strong><p>{caption}</p></div></figcaption></figure>')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><style>
:root{{color-scheme:dark;background:#171919;color:#e1eaec;font-family:"Plus Jakarta Sans Variable",system-ui,sans-serif}}
*{{box-sizing:border-box}}body{{margin:0}}main{{max-width:1280px;margin:auto;padding:clamp(20px,4vw,60px)}}
header{{margin-bottom:40px;border-bottom:1px solid #3a3d3e;padding-bottom:24px}}
h1{{font-size:clamp(26px,4vw,48px);line-height:1.15;overflow-wrap:anywhere;margin:0 0 16px}}
header p{{max-width:65ch;color:#b4bcbe;line-height:1.6;margin:0}}
.gallery{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:32px 24px}}
figure{{margin:0;min-width:0}}img{{display:block;width:100%;height:320px;object-fit:contain;background:#1e2121}}
figcaption{{display:flex;gap:12px;padding:16px 0}}.number{{color:#6bdbd3;font-variant-numeric:tabular-nums}}
strong{{font-size:15px;overflow-wrap:anywhere}}figcaption p{{font-size:14px;line-height:1.5;color:#b4bcbe;overflow-wrap:anywhere;margin:8px 0}}
::selection{{background:#6bdbd3;color:#101416}}@media(max-width:480px){{img{{height:280px}}header{{margin-bottom:28px}}}}
@media print{{:root{{color-scheme:light;background:white;color:black}}img{{background:white}}figure{{break-inside:avoid}}}}
</style></head><body><main><header><h1>{html.escape(title)}</h1>
<p>{len(entries)} photos in selection order. Preview images are included in this file.
Original paths and stable photo IDs are recorded in manifest.json.</p></header>
<section class="gallery" aria-label="Photo selection">{''.join(figures)}</section>
</main></body></html>'''


def create(library, ids: list[str], title: str) -> dict:
    from .library import NotFoundError, ValidationError

    if not isinstance(ids, list) or not 1 <= len(ids) <= MAX_ITEMS:
        raise ValidationError(f"ids must contain 1-{MAX_ITEMS} photo ids in the desired order")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 160:
        raise ValidationError("title must contain 1-160 characters")
    title = title.strip()
    entries, images, sheet_items, omitted = [], [], [], []
    for position, photo_id in enumerate(ids, 1):
        try:
            row = library._resolve_photo(photo_id, None)
        except NotFoundError:
            omitted.append({"requested_n": position, "id": str(photo_id), "reason": "not_found"})
            continue
        if row["missing"] or not Path(row["path"]).is_file():
            omitted.append({"requested_n": position, "id": row["id"], "reason": "original_missing"})
            continue
        try:
            signature_before = stat_signature(Path(row["path"]))
            actual_hash = content_hash(Path(row["path"]))
            with Image.open(row["path"]) as original:
                width, height = original.size
            image = library.render_preview(row["id"], size=512, max_bytes=200 * 1024)
            if stat_signature(Path(row["path"])) != signature_before:
                omitted.append({"requested_n": position, "id": row["id"], "reason": "original_changed"})
                continue
            with Image.open(io.BytesIO(image)) as preview:
                preview_width, preview_height = preview.size
        except NotFoundError:
            omitted.append({"requested_n": position, "id": row["id"], "reason": "original_missing"})
            continue
        except (OSError, ValueError):
            omitted.append({"requested_n": position, "id": row["id"], "reason": "unreadable"})
            continue
        n = len(entries) + 1
        entry = {"n": n, "requested_n": position, "id": row["id"], "path": row["path"],
                 "content_hash": actual_hash, "indexed_metadata_stale": actual_hash != row["content_hash"],
                 "width": width, "height": height,
                 "preview_width": preview_width, "preview_height": preview_height,
                 "taken_at": row["taken_at"], "caption": row["caption"] or "",
                 "preview_sha256": hashlib.sha256(image).hexdigest()}
        entries.append(entry)
        images.append(image)
        sheet_items.append(ContactSheetItem(thumb_path(library.settings.thumbs_dir, row["id"]), n,
                                            Path(row["path"]).name, image_bytes=image))
    if not entries:
        raise ValidationError("No readable photos to export. Use ids from photos_search and check that their originals are available.")
    columns = min(5, len(entries))
    for i, entry in enumerate(entries):
        entry.update({"row": i // columns + 1, "column": i % columns + 1})
    manifest = {"schema": 1, "title": title, "requested": len(ids), "returned": len(entries),
                "complete": not omitted, "columns": columns, "omitted": omitted, "photos": entries}
    page = _gallery(title, entries, images)
    sheet = render_contact_sheet(sheet_items, cols=columns)
    signature = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
    export_id = hashlib.sha256(signature + page.encode("utf-8") + sheet).hexdigest()[:32]
    folder = library.settings.data_dir / "exports" / export_id
    folder.mkdir(parents=True, exist_ok=True)
    files = {"gallery": folder / "gallery.html", "manifest": folder / "manifest.json",
             "contact_sheet": folder / "contact-sheet.jpg"}
    write_text_atomic(files["gallery"], page)
    write_bytes_atomic(files["contact_sheet"], sheet)
    write_json_atomic(files["manifest"], manifest)
    return {"id": export_id, "title": title, "requested": len(ids), "returned": len(entries),
            "complete": not omitted, "omitted": omitted,
            "photos": [{k: e[k] for k in ("n", "requested_n", "id", "path", "row", "column")} for e in entries],
            "files": {k: str(v.resolve()) for k, v in files.items()},
            "gallery_url": f"http://127.0.0.1:{library.settings.port}/api/exports/{export_id}/gallery.html"}

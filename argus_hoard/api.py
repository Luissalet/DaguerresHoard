"""FastAPI application: HTTP surface for the UI and for the agent
(`/api/agent/*`, which returns exactly what the MCP adapter returns).

UI routes and agent routes share the same `Library` calls; only the agent
routes are written to the `agent_calls` audit table, so "What the
assistant did" never shows the human's own clicks."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__, db as dbmod
from .config import DISPLAY_NAME, SERVICE_SLUG, Settings
from .guard import GuardMiddleware
from .library import ID_RE, Library, NotFoundError, ValidationError

NO_UI_HTML = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{DISPLAY_NAME}</title></head>
<body style="font-family: system-ui; max-width: 640px; margin: 4rem auto; color: #222">
<h1>{DISPLAY_NAME}</h1>
<p>The API is running, but the frontend has not been built yet.</p>
<pre>cd frontend
npm ci
npm run build</pre>
<p>Then restart the app. The API itself is usable at <code>/api/health</code>.</p>
</body></html>"""


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class SearchBody(BaseModel):
    query: str
    filters: dict = Field(default_factory=dict)
    limit: int = 12
    contact_sheet: bool = True


class SimilarBody(BaseModel):
    photo_id: str | None = None
    path: str | None = None
    limit: int = 12
    contact_sheet: bool = True


class ShowBody(BaseModel):
    ids: list[str]
    size: int = 768


class DescribeBody(BaseModel):
    photo_id: str
    caption: bool = False


class DuplicatesBody(BaseModel):
    kind: str = "exact"
    limit: int = 10


class TimelineBody(BaseModel):
    year: int | None = None


class AddFolderBody(BaseModel):
    path: str


class AlbumBody(BaseModel):
    name: str
    photo_ids: list[str] = Field(default_factory=list)


class AlbumRemoveBody(BaseModel):
    photo_ids: list[str]


class RootBody(BaseModel):
    path: str
    excluded_globs: list[str] = Field(default_factory=list)


class RootExcludesBody(BaseModel):
    excluded_globs: list[str]


class ScanBody(BaseModel):
    root_id: int | None = None


class SettingsBody(BaseModel):
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    translate_search: bool | None = None


class CaptionBatchBody(BaseModel):
    limit: int = 500


class BackendConfigBody(BaseModel):
    """PUT /api/backend/config -- UI only, never an agent endpoint. Every
    field is optional and an empty string clears that override; None
    leaves it untouched. The token is write-only: it is never read back."""

    faustus_url: str | None = None
    faustus_token: str | None = None
    vision_url: str | None = None
    vision_model: str | None = None
    llm_url: str | None = None
    llm_model: str | None = None


def _summarise_validation(exc: RequestValidationError) -> str:
    parts = []
    for err in exc.errors()[:5]:
        loc_parts = list(err.get("loc", ()))
        if loc_parts and loc_parts[0] in ("body", "query", "path"):
            loc_parts = loc_parts[1:]
        loc = ".".join(str(x) for x in loc_parts)
        parts.append(f"{loc or 'body'}: {err.get('msg', 'invalid')}")
    return "; ".join(parts) or "invalid request"


def _check_id(photo_id: str) -> str:
    if not ID_RE.match(photo_id or ""):
        raise ApiError(400, "invalid_argument", "photo ids are 32 lowercase hex characters")
    return photo_id


def _check_optional_url(field: str, value: str | None) -> None:
    """An empty string clears an override and is always fine; a non-empty
    value must look like an http(s) URL (same check as the Ollama field)."""
    if not value:
        return
    parsed = urlparse(value.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ApiError(400, "invalid_argument", f"{field} must look like http://127.0.0.1:PORT")


def create_app(data_dir: Path, static_dir: Path | None = None, port: int = 8814) -> FastAPI:
    settings = Settings(data_dir=data_dir, port=port)
    lib = Library(settings)

    app = FastAPI(title=DISPLAY_NAME, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(GuardMiddleware, port=port)
    app.state.library = lib

    # -- error shape: always {"error": code, "message": text} ------------- #
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return JSONResponse({"error": exc.code, "message": exc.message}, status_code=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "request failed"
        if exc.status_code == 404:
            message = f"no such endpoint: {request.url.path}"
        return JSONResponse({"error": code, "message": message}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        message = _summarise_validation(exc)
        path = request.url.path
        if path.startswith("/api/agent/"):
            lib.log_agent_call(path.rsplit("/", 1)[-1], "(rejected: invalid arguments)", False, 0.0, message)
        return JSONResponse({"error": "invalid_argument", "message": message}, status_code=400)

    def run(fn, *, tool: str | None = None, args: dict | None = None) -> Any:
        """Run a Library call, map its errors, and audit it when `tool` is set."""
        start = time.perf_counter()
        try:
            result = fn()
        except (ValidationError, NotFoundError) as exc:
            if tool:
                lib.log_agent_call(tool, _args_summary(args), False, (time.perf_counter() - start) * 1000, str(exc))
            if isinstance(exc, NotFoundError):
                raise ApiError(404, "not_found", str(exc)) from None
            raise ApiError(400, "invalid_argument", str(exc)) from None
        except Exception as exc:  # noqa: BLE001
            if tool:
                lib.log_agent_call(tool, _args_summary(args), False, (time.perf_counter() - start) * 1000, str(exc))
            raise ApiError(500, "internal_error", f"{type(exc).__name__}: {exc}") from None
        if tool:
            lib.log_agent_call(tool, _args_summary(args), True, (time.perf_counter() - start) * 1000, None)
        return result

    # -- health -------------------------------------------------------- #
    @app.get("/api/health")
    def health():
        c = lib.conn
        return {
            "service": SERVICE_SLUG,
            "name": DISPLAY_NAME,
            "version": __version__,
            "status": "ok",
            "photo_count": c.execute("SELECT COUNT(*) c FROM photos WHERE missing = 0").fetchone()["c"],
            "roots": c.execute("SELECT COUNT(*) c FROM roots").fetchone()["c"],
            "embedder": lib.embedder.name,
        }

    # -- library / roots / jobs (UI) ------------------------------------ #
    @app.get("/api/library")
    def library_status():
        return lib.library_status()

    @app.get("/api/places")
    def places():
        return lib.places()

    @app.get("/api/photos")
    def list_photos(
        limit: int = 60,
        offset: int = 0,
        taken_after: str | None = None,
        taken_before: str | None = None,
        year: int | None = None,
        month: int | None = None,
        place: str | None = None,
        folder: str | None = None,
        camera: str | None = None,
        orientation: str | None = None,
        min_megapixels: float | None = None,
        has_gps: bool | None = None,
    ):
        filters = {
            k: v
            for k, v in dict(
                taken_after=taken_after, taken_before=taken_before, year=year, month=month,
                place=place, folder=folder, camera=camera, orientation=orientation,
                min_megapixels=min_megapixels, has_gps=has_gps,
            ).items()
            if v is not None
        }
        return run(lambda: lib.list_photos(filters=filters, limit=limit, offset=offset))

    @app.get("/api/photos/{photo_id}")
    def get_photo(photo_id: str):
        _check_id(photo_id)
        return run(lambda: lib.describe(photo_id, caption=False))

    @app.get("/api/photos/{photo_id}/thumbnail")
    def get_thumbnail(photo_id: str):
        from .thumbnails import thumb_path

        _check_id(photo_id)
        p = thumb_path(settings.thumbs_dir, photo_id)
        if not p.exists():
            raise ApiError(404, "not_found", "thumbnail not ready")
        return FileResponse(p, media_type="image/webp", headers={"Cache-Control": "private, max-age=3600"})

    @app.get("/api/photos/{photo_id}/preview")
    def get_preview(photo_id: str, size: int = 1600):
        """Large JPEG of the original for the lightbox (handles HEIC/TIFF,
        which browsers cannot show, and EXIF rotation)."""
        _check_id(photo_id)
        data = run(lambda: lib.render_preview(photo_id, size=size))
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=600"})

    @app.post("/api/photos/{photo_id}/open")
    def open_in_explorer(photo_id: str):
        _check_id(photo_id)
        row = run(lambda: lib._resolve_photo(photo_id, None))
        path = Path(row["path"])
        if not sys.platform.startswith("win"):
            raise ApiError(400, "unsupported_platform", "Open in Explorer only works on Windows.")
        if not path.exists():
            raise ApiError(404, "not_found", f"the file is not reachable right now: {path}")
        # explorer parses its own command line: `/select,"<path>"` is the
        # form that survives spaces and commas. Paths cannot contain quotes.
        subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')  # noqa: S602 - no shell, fixed exe
        return {"ok": True}

    @app.get("/api/roots")
    def list_roots():
        return lib.list_roots()

    @app.post("/api/roots")
    def add_root(body: RootBody):
        return run(lambda: lib.add_root(body.path, added_by="user", excluded_globs=body.excluded_globs))

    @app.put("/api/roots/{root_id}")
    def update_root(root_id: int, body: RootExcludesBody):
        return run(lambda: lib.update_root_excludes(root_id, body.excluded_globs))

    @app.delete("/api/roots/{root_id}")
    def remove_root(root_id: int):
        run(lambda: lib.remove_root(root_id))
        return {"ok": True}

    @app.post("/api/scan")
    def start_scan(body: ScanBody):
        return {"job_id": run(lambda: lib.start_scan(body.root_id))}

    @app.get("/api/jobs")
    def list_jobs(limit: int = 10):
        return lib.jobs.list(limit=limit)

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        job = lib.jobs.get(job_id)
        if not job:
            raise ApiError(404, "not_found", "job not found")
        return job

    # -- UI versions of the search tools (not audited) --------------------- #
    @app.post("/api/search")
    def ui_search(body: SearchBody):
        # UI-only: automatically translates a non-English query to English
        # first (the MCP tool tells the agent to translate itself instead,
        # so /api/agent/photos_search below always calls lib.search directly).
        return run(lambda: lib.search_translated(body.query, body.filters, body.limit, False))

    @app.post("/api/similar")
    def ui_similar(body: SimilarBody):
        return run(lambda: lib.similar(body.photo_id, body.path, body.limit, False))

    @app.post("/api/duplicates")
    def ui_duplicates(body: DuplicatesBody):
        return run(lambda: lib.duplicates(body.kind, body.limit))

    @app.get("/api/timeline")
    def ui_timeline(year: int | None = None, samples: int = 4):
        return run(lambda: lib.timeline(year, samples=max(0, min(samples, 8))))

    @app.post("/api/photos/{photo_id}/caption")
    def ui_caption(photo_id: str):
        _check_id(photo_id)
        return run(lambda: lib.describe(photo_id, caption=True))

    # -- albums ---------------------------------------------------------- #
    @app.get("/api/albums")
    def list_albums():
        return lib.list_albums()

    @app.get("/api/albums/{album_id}")
    def get_album(album_id: str):
        return run(lambda: lib.get_album(album_id))

    @app.post("/api/albums")
    def create_album(body: AlbumBody):
        return run(lambda: lib.album(body.name, body.photo_ids, created_by="user"))

    @app.post("/api/albums/{album_id}/remove")
    def album_remove(album_id: str, body: AlbumRemoveBody):
        return run(lambda: lib.remove_from_album(album_id, body.photo_ids))

    @app.delete("/api/albums/{album_id}")
    def delete_album(album_id: str):
        run(lambda: lib.delete_album(album_id))
        return {"ok": True}

    # -- settings, model, geodata, captions ---------------------------------- #
    @app.get("/api/settings")
    def get_settings():
        from .captions import DEFAULT_BASE_URL, DEFAULT_MODEL

        return {
            "ollama_base_url": dbmod.get_setting(lib.conn, "ollama_base_url", DEFAULT_BASE_URL),
            "ollama_model": dbmod.get_setting(lib.conn, "ollama_model", DEFAULT_MODEL),
            "translate_search": lib.translate_search_enabled(),
        }

    @app.post("/api/settings")
    def set_settings(body: SettingsBody):
        changed_legacy_vision = False
        if body.ollama_base_url is not None:
            parsed = urlparse(body.ollama_base_url.strip())
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                raise ApiError(400, "invalid_argument", "the Ollama URL must look like http://127.0.0.1:11434")
            dbmod.set_setting(lib.conn, "ollama_base_url", body.ollama_base_url.strip().rstrip("/"))
            changed_legacy_vision = True
        if body.ollama_model is not None:
            if not body.ollama_model.strip():
                raise ApiError(400, "invalid_argument", "the model name cannot be empty")
            dbmod.set_setting(lib.conn, "ollama_model", body.ollama_model.strip())
            changed_legacy_vision = True
        if body.translate_search is not None:
            lib.set_translate_search(body.translate_search)
        if changed_legacy_vision:
            # The legacy Ollama fields feed the `vision` capability's
            # explicit override (see backend.py); rebuild it so a saved
            # change takes effect on the next caption without a restart.
            lib.backend.reload()
        return get_settings()

    @app.post("/api/settings/ollama/test")
    def test_ollama():
        result = lib._captioner().test_connection()
        return {"ok": result.ok, "error": result.error}

    @app.post("/api/captions/batch")
    def caption_batch(body: CaptionBatchBody):
        return {"job_id": run(lambda: lib.start_caption_batch(body.limit))}

    @app.get("/api/model")
    def model_status():
        return lib.model_status()

    @app.post("/api/model/download")
    def model_download():
        return {"job_id": run(lib.start_model_download)}

    @app.post("/api/geocoder/download")
    def geocoder_download():
        return {"job_id": run(lib.start_geodata_download)}

    # -- shared model backend (Hoard Link) -- UI only, never agent routes -- #
    @app.get("/api/backend")
    def get_backend():
        return lib.backend_status()

    @app.put("/api/backend/config")
    def set_backend_config(body: BackendConfigBody):
        _check_optional_url("faustus_url", body.faustus_url)
        _check_optional_url("vision_url", body.vision_url)
        _check_optional_url("llm_url", body.llm_url)
        lib.backend.set_overrides(
            faustus_url=body.faustus_url,
            faustus_token=body.faustus_token,
            capability_overrides={
                "vision": (body.vision_url, body.vision_model),
                "llm": (body.llm_url, body.llm_model),
            },
        )
        return lib.backend_status()

    @app.post("/api/backend/recheck")
    def recheck_backend():
        lib.backend.reload()
        return lib.backend_status()

    # -- agent activity log ------------------------------------------------ #
    @app.get("/api/agent-calls")
    def agent_calls(limit: int = 20):
        return lib.recent_agent_calls(limit=limit)

    # -- agent tools (mirror the MCP tools one to one, audited) -------------- #
    @app.post("/api/agent/photos_search")
    def agent_search(body: SearchBody):
        return run(lambda: lib.search(body.query, body.filters, body.limit, body.contact_sheet),
                   tool="photos_search", args=body.model_dump())

    @app.post("/api/agent/photos_similar")
    def agent_similar(body: SimilarBody):
        return run(lambda: lib.similar(body.photo_id, body.path, body.limit, body.contact_sheet),
                   tool="photos_similar", args=body.model_dump())

    @app.post("/api/agent/photos_show")
    def agent_show(body: ShowBody):
        return run(lambda: lib.show(body.ids, body.size), tool="photos_show", args=body.model_dump())

    @app.post("/api/agent/photos_describe")
    def agent_describe(body: DescribeBody):
        return run(lambda: lib.describe(body.photo_id, body.caption), tool="photos_describe", args=body.model_dump())

    @app.post("/api/agent/photos_duplicates")
    def agent_duplicates(body: DuplicatesBody):
        return run(lambda: lib.duplicates(body.kind, body.limit), tool="photos_duplicates", args=body.model_dump())

    @app.post("/api/agent/photos_timeline")
    def agent_timeline(body: TimelineBody):
        return run(lambda: lib.timeline(body.year), tool="photos_timeline", args=body.model_dump())

    @app.post("/api/agent/photos_library")
    def agent_library():
        return run(lambda: lib.library_status(compact=True), tool="photos_library", args={})

    @app.post("/api/agent/photos_add_folder")
    def agent_add_folder(body: AddFolderBody):
        def do():
            root = lib.add_root(body.path, added_by="agent")
            job_id = lib.start_scan(root["id"])
            return {"root": {k: root[k] for k in ("id", "path", "photo_count")}, "job_id": job_id,
                    "next": "indexing runs in the background; call photos_library to see progress"}

        return run(do, tool="photos_add_folder", args=body.model_dump())

    @app.post("/api/agent/photos_album")
    def agent_album(body: AlbumBody):
        return run(lambda: lib.album(body.name, body.photo_ids, created_by="agent"),
                   tool="photos_album", args=body.model_dump())

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def api_not_found(rest: str):
        raise ApiError(404, "not_found", f"no such endpoint: /api/{rest}")

    # -- static frontend -------------------------------------------------- #
    if static_dir and (static_dir / "index.html").exists():
        dist = static_dir.resolve()
        if (dist / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{full_path:path}")
        def spa(full_path: str):
            if full_path:
                candidate = (dist / full_path).resolve()
                # only files that really live inside dist/ (no ../ escapes)
                if candidate.is_file() and candidate.is_relative_to(dist):
                    return FileResponse(candidate)
            return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})
    else:

        @app.get("/")
        def no_ui():
            return HTMLResponse(NO_UI_HTML)

    return app


def _args_summary(args: dict | None) -> str:
    """Short, human-readable argument summary for the audit log."""
    if not args:
        return ""
    parts = []
    for k, v in args.items():
        if v in (None, "", [], {}) or (k == "contact_sheet" and v is True):
            continue
        if isinstance(v, list):
            text = f"[{len(v)} items]" if len(v) > 3 else ", ".join(str(x)[:12] for x in v)
        elif isinstance(v, dict):
            text = ", ".join(f"{a}={b}" for a, b in v.items() if b not in (None, ""))
        else:
            text = str(v)
        parts.append(f"{k}={text[:120]}")
    return "; ".join(parts)

"""FastAPI application: HTTP surface for the UI and for the agent
(`/api/agent/*`, which returns exactly what the MCP adapter returns)."""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, db as dbmod
from .config import DISPLAY_NAME, SERVICE_SLUG, Settings
from .geocode import download_geonames
from .guard import GuardMiddleware
from .library import Library, NotFoundError, ValidationError

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


class RootBody(BaseModel):
    path: str
    excluded_globs: list[str] = Field(default_factory=list)


class ScanBody(BaseModel):
    root_id: int | None = None


class SettingsBody(BaseModel):
    ollama_base_url: str | None = None
    ollama_model: str | None = None


def create_app(data_dir: Path, static_dir: Path | None = None, port: int = 8814) -> FastAPI:
    settings = Settings(data_dir=data_dir, port=port)
    lib = Library(settings)

    app = FastAPI(title=DISPLAY_NAME, docs_url=None, redoc_url=None)
    app.add_middleware(GuardMiddleware, port=port)
    app.state.library = lib

    def call_agent_tool(tool: str, fn, args_summary: dict) -> Any:
        start = time.perf_counter()
        try:
            result = fn()
            duration = (time.perf_counter() - start) * 1000
            lib.log_agent_call(tool, str(args_summary), True, duration, None)
            return result
        except (ValidationError, NotFoundError) as exc:
            duration = (time.perf_counter() - start) * 1000
            lib.log_agent_call(tool, str(args_summary), False, duration, str(exc))
            code = "not_found" if isinstance(exc, NotFoundError) else "invalid_argument"
            status = 404 if isinstance(exc, NotFoundError) else 400
            raise HTTPException(status_code=status, detail={"error": code, "message": str(exc)})
        except Exception as exc:  # noqa: BLE001
            duration = (time.perf_counter() - start) * 1000
            lib.log_agent_call(tool, str(args_summary), False, duration, str(exc))
            raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(exc)})

    # -- health -------------------------------------------------------- #
    @app.get("/api/health")
    def health():
        status = lib.library_status()
        return {
            "service": SERVICE_SLUG,
            "name": DISPLAY_NAME,
            "version": __version__,
            "status": "ok",
            "photo_count": status["photo_count"],
            "roots": len(status["roots"]),
            "embedder": status["embedder"]["name"],
        }

    # -- library / roots / jobs (UI) ------------------------------------ #
    @app.get("/api/library")
    def library_status():
        return lib.library_status()

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
        return lib.list_photos(filters=filters, limit=limit, offset=offset)

    @app.get("/api/photos/{photo_id}")
    def get_photo(photo_id: str):
        try:
            return lib.describe(photo_id, caption=False)
        except NotFoundError as exc:
            raise HTTPException(404, {"error": "not_found", "message": str(exc)})

    @app.get("/api/photos/{photo_id}/thumbnail")
    def get_thumbnail(photo_id: str):
        from .thumbnails import thumb_path

        p = thumb_path(settings.thumbs_dir, photo_id)
        if not p.exists():
            raise HTTPException(404, {"error": "not_found", "message": "thumbnail not ready"})
        return FileResponse(p, media_type="image/webp")

    @app.post("/api/photos/{photo_id}/open")
    def open_in_explorer(photo_id: str):
        try:
            row = lib._resolve_photo(photo_id, None)
        except NotFoundError as exc:
            raise HTTPException(404, {"error": "not_found", "message": str(exc)})
        if not sys.platform.startswith("win"):
            return JSONResponse(
                {"error": "unsupported_platform", "message": "Open in Explorer only works on Windows."},
                status_code=400,
            )
        import subprocess

        subprocess.Popen(["explorer", f"/select,{row['path']}"])
        return {"ok": True}

    @app.get("/api/roots")
    def list_roots():
        return lib.list_roots()

    @app.post("/api/roots")
    def add_root(body: RootBody):
        try:
            return lib.add_root(body.path, added_by="user", excluded_globs=body.excluded_globs)
        except ValidationError as exc:
            raise HTTPException(400, {"error": "invalid_argument", "message": str(exc)})

    @app.delete("/api/roots/{root_id}")
    def remove_root(root_id: int):
        lib.remove_root(root_id)
        return {"ok": True}

    @app.post("/api/scan")
    def start_scan(body: ScanBody):
        job_id = lib.start_scan(body.root_id)
        return {"job_id": job_id}

    @app.get("/api/jobs")
    def list_jobs(limit: int = 10):
        return lib.jobs.list(limit=limit)

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        job = lib.jobs.get(job_id)
        if not job:
            raise HTTPException(404, {"error": "not_found", "message": "job not found"})
        return job

    # -- albums ---------------------------------------------------------- #
    @app.get("/api/albums")
    def list_albums():
        return lib.list_albums()

    @app.get("/api/albums/{album_id}")
    def get_album(album_id: str):
        try:
            return lib.get_album(album_id)
        except NotFoundError as exc:
            raise HTTPException(404, {"error": "not_found", "message": str(exc)})

    @app.post("/api/albums")
    def create_album(body: AlbumBody):
        return lib.album(body.name, body.photo_ids)

    # -- settings ---------------------------------------------------------- #
    @app.get("/api/settings")
    def get_settings():
        from .captions import DEFAULT_BASE_URL, DEFAULT_MODEL

        return {
            "ollama_base_url": dbmod.get_setting(lib.conn, "ollama_base_url", DEFAULT_BASE_URL),
            "ollama_model": dbmod.get_setting(lib.conn, "ollama_model", DEFAULT_MODEL),
        }

    @app.post("/api/settings")
    def set_settings(body: SettingsBody):
        if body.ollama_base_url is not None:
            dbmod.set_setting(lib.conn, "ollama_base_url", body.ollama_base_url)
        if body.ollama_model is not None:
            dbmod.set_setting(lib.conn, "ollama_model", body.ollama_model)
        return get_settings()

    @app.post("/api/settings/ollama/test")
    def test_ollama():
        captioner = lib._captioner()
        result = captioner.test_connection()
        return {"ok": result.ok, "error": result.error}

    @app.post("/api/geocoder/download")
    def geocoder_download():
        job_id = lib.jobs.start(
            "geocode_download",
            lambda handle: (handle.progress(0.1, "downloading"), download_geonames(settings.geodata_dir), handle.progress(1.0, "done")),
        )
        return {"job_id": job_id}

    # -- agent activity log ------------------------------------------------ #
    @app.get("/api/agent-calls")
    def agent_calls(limit: int = 20):
        return lib.recent_agent_calls(limit=limit)

    # -- agent tools (mirrors MCP) ------------------------------------------ #
    @app.post("/api/agent/photos_search")
    def agent_search(body: SearchBody):
        return call_agent_tool(
            "photos_search",
            lambda: lib.search(body.query, body.filters, body.limit, body.contact_sheet),
            body.model_dump(),
        )

    @app.post("/api/agent/photos_similar")
    def agent_similar(body: SimilarBody):
        return call_agent_tool(
            "photos_similar",
            lambda: lib.similar(body.photo_id, body.path, body.limit, body.contact_sheet),
            body.model_dump(),
        )

    @app.post("/api/agent/photos_show")
    def agent_show(body: ShowBody):
        return call_agent_tool("photos_show", lambda: {"images": lib.show(body.ids, body.size)}, body.model_dump())

    @app.post("/api/agent/photos_describe")
    def agent_describe(body: DescribeBody):
        return call_agent_tool(
            "photos_describe", lambda: lib.describe(body.photo_id, body.caption), body.model_dump()
        )

    @app.post("/api/agent/photos_duplicates")
    def agent_duplicates(body: DuplicatesBody):
        return call_agent_tool(
            "photos_duplicates", lambda: lib.duplicates(body.kind, body.limit), body.model_dump()
        )

    @app.post("/api/agent/photos_timeline")
    def agent_timeline(body: TimelineBody):
        return call_agent_tool("photos_timeline", lambda: lib.timeline(body.year), body.model_dump())

    @app.post("/api/agent/photos_library")
    def agent_library():
        return call_agent_tool("photos_library", lambda: lib.library_status(), {})

    @app.post("/api/agent/photos_add_folder")
    def agent_add_folder(body: AddFolderBody):
        def do():
            root = lib.add_root(body.path, added_by="agent")
            job_id = lib.start_scan(root["id"])
            return {"root": root, "job_id": job_id}

        return call_agent_tool("photos_add_folder", do, body.model_dump())

    @app.post("/api/agent/photos_album")
    def agent_album(body: AlbumBody):
        return call_agent_tool("photos_album", lambda: lib.album(body.name, body.photo_ids), body.model_dump())

    # -- static frontend -------------------------------------------------- #
    if static_dir and static_dir.exists() and (static_dir / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/{full_path:path}")
        def spa(full_path: str):
            candidate = static_dir / full_path
            if full_path and candidate.exists() and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(static_dir / "index.html")
    else:

        @app.get("/")
        def no_ui():
            return HTMLResponse(NO_UI_HTML)

    return app

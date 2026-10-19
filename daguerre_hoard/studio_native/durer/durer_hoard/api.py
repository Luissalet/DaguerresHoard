from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import re
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ROOT, settings
from .native import catalog, dispatch, executable, launch_gui, gui_executable, failed_results
from .history import execute as history_execute
from .sessions import sessions
from .thumbnails import thumbnail as gallery_thumbnail
from . import store

router = APIRouter()
COPILOT_INSTALLED = True
HOARDLINK_AVAILABLE = True


class CreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    width: float | None = Field(default=None, gt=0, le=100000)
    height: float | None = Field(default=None, gt=0, le=100000)
    units: Literal["Pixels", "Points", "Picas", "Inches", "Millimeters", "Centimeters", "Feet", "Yards", "Meters", "Feet & Inches"] | None = None


class ActionsRequest(BaseModel):
    actions: list[dict[str, Any]] = Field(min_length=1, max_length=80)


class ExportRequest(BaseModel):
    format: str
    arguments: dict[str, Any] = Field(default_factory=dict)


def _project(project_id: str):
    try:
        item = store.read(project_id)
        root = store.project_root(project_id)
        return item, root
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "durer_hoard" / "static" / "index.html").read_text(encoding="utf-8")


@router.get("/api/health")
def health():
    configured = ROOT / "native/bin" / ("durer-cli.exe" if os.name == "nt" else "durer-cli")
    gui = gui_executable()
    return {"ok": True, "service": "durers-hoard", "hoard_link": HOARDLINK_AVAILABLE, "copilot": COPILOT_INSTALLED,
            "engine_configured": bool(configured and configured.is_file()),
            "gui_configured": bool(gui and gui.is_file()),
            "engine_path": str(configured) if configured else None, "data_dir": str(settings().data_dir),
            }


@router.get("/api/catalog")
def get_catalog():
    try:
        return catalog()
    except Exception as exc:
        raise HTTPException(503, f"Native engine discovery failed: {exc}") from exc


@router.get("/api/engine/catalog")
def engine_catalog():
    return get_catalog()


@router.get("/api/operations/{operation_id}")
def operation(operation_id: str):
    record = sessions.operation(operation_id)
    if not record:
        raise HTTPException(404, "Operation receipt not found in this service lifetime")
    return record


@router.get("/api/illustrations")
def illustrations():
    return store.list_projects()


@router.post("/api/illustrations")
def new_illustration(payload: CreateRequest):
    try:
        canvas, native_canvas = store.canvas_settings(payload.width, payload.height, payload.units)
        item = store.create(payload.title, canvas=canvas)
        project, root = _project(item["id"])
        results = sessions.execute(item["id"], root / "project.durer", [], new_document=native_canvas)
        return {**project, "results": results}
    except Exception as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/api/illustrations/import")
async def import_illustration(title: str, file: UploadFile = File(...)):
    filename = Path(file.filename or "source").name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".svg", ".png", ".jpg", ".jpeg", ".webp", ".pdf", ".durer", ".vectorcraft", ".drawcraft"}:
        raise HTTPException(415, "Import supports SVG, PNG, JPEG, WebP, and PDF files")
    data_dir = settings().data_dir / "staging"
    data_dir.mkdir(parents=True, exist_ok=True)
    staged = data_dir / f"{uuid.uuid4().hex}{suffix}"
    contents = await file.read(50 * 1024 * 1024 + 1)
    if not contents or len(contents) > 50 * 1024 * 1024:
        raise HTTPException(413, "File must be between 1 byte and 50 MB")
    staged.write_bytes(contents)
    try:
        item = store.create(title, source=staged, source_name=filename)
        project, root = _project(item["id"])
        source_path = item["source"]["path"]
        results = await asyncio.to_thread(
            sessions.execute, item["id"], root / "project.durer",
            [{"name": "open_file", "arguments": {"path": source_path}}])
        return {**project, "results": results}
    except Exception as exc:
        raise HTTPException(503, f"Import was copied but native open failed: {exc}") from exc
    finally:
        staged.unlink(missing_ok=True)


@router.get("/api/illustrations/{project_id}")
def illustration(project_id: str):
    item, _ = _project(project_id)
    return item


@router.post("/api/illustrations/{project_id}/actions")
def actions(project_id: str, payload: ActionsRequest):
    item, root = _project(project_id)
    try:
        results = history_execute(project_id, root / "project.durer", payload.actions)
        result = {"illustration": store.read(project_id), "results": results}
        return JSONResponse(result, status_code=502) if failed_results(results) else result
    except Exception as exc:
        raise HTTPException(502, f"Dürer action failed: {exc}") from exc


@router.post("/api/illustrations/{project_id}/export")
def export(project_id: str, payload: ExportRequest):
    _, root = _project(project_id)
    fmt = payload.format.lower().lstrip(".")
    if fmt not in {"svg", "png", "pdf", "jpg", "webp", "gif", "tiff", "bmp", "dxf", "eps", "emf", "wmf", "psd", "durer", "vectorcraft"}:
        raise HTTPException(415, "Format is not in the native export schema")
    path = root / "exports" / f"{project_id}-{uuid.uuid4().hex}.{fmt}"
    args = {**payload.arguments, "format": "durer" if fmt == "vectorcraft" else fmt, "path": str(path)}
    try:
        results = sessions.execute(project_id, root / "project.durer",
                                   [{"name": "export", "arguments": args}])
        if any(row.get("name") == "export" and row.get("is_error") for row in results):
            raise RuntimeError("Dürer reported an export error")
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("Native export reported success but produced no file")
        return {"format": fmt, "path": str(path), "url": f"/api/illustrations/{project_id}/files/exports/{path.name}",
                "bytes": path.stat().st_size, "results": results}
    except Exception as exc:
        raise HTTPException(502, f"Native export failed: {exc}") from exc


@router.get("/api/illustrations/{project_id}/files/{area}/{filename}")
def file(project_id: str, area: str, filename: str):
    _, root = _project(project_id)
    if area not in {"exports", "sources"} or Path(filename).name != filename:
        raise HTTPException(404, "File not found")
    target = (root / area / filename).resolve()
    if not target.is_relative_to((root / area).resolve()) or not target.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(target, filename=target.name)


@router.get("/api/illustrations/{project_id}/preview")
def preview(project_id: str):
    _, root = _project(project_id)
    path = root / "exports" / f"preview-{uuid.uuid4().hex}.png"
    try:
        results = sessions.execute(project_id, root / "project.durer",
                                   [{"name": "export", "arguments": {"format": "png", "path": str(path), "scale": 1}}])
        if any(row.get("name") == "export" and row.get("is_error") for row in results):
            raise RuntimeError("Dürer reported a preview export error")
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("Native preview export returned no PNG")
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})
    except Exception as exc:
        raise HTTPException(502, f"Preview render failed: {exc}") from exc


@router.get("/api/illustrations/{project_id}/thumbnail")
def thumbnail(project_id: str, refresh: bool = False):
    _, root = _project(project_id)
    try:
        path, hit = gallery_thumbnail(root / "project.durer", refresh=refresh)
        return FileResponse(path, media_type="image/png", headers={
            "Cache-Control": "no-cache", "X-Durer-Thumbnail-Cache": "hit" if hit else "miss"})
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Thumbnail render failed: {exc}") from exc


@router.get("/api/illustrations/{project_id}/native")
def native_file(project_id: str):
    _, root = _project(project_id)
    path = root / "project.durer"
    if not path.is_file() and path.with_name("project.vectorcraft").is_file():
        sessions.execute(project_id, path, [])
    if not path.is_file():
        raise HTTPException(404, "Native project is not saved")
    return FileResponse(path, filename=f"{project_id}.durer")


@router.post("/api/illustrations/{project_id}/open-gui")
def open_gui(project_id: str):
    _, root = _project(project_id)
    try:
        gui = launch_gui(project_id)
        sessions.connect(project_id, gui["address"])
        results = sessions.execute(project_id, root / "project.durer", [])
        if any(row.get("is_error") for row in results):
            raise RuntimeError("Dürer GUI did not open the native project")
        return {**gui, "project_file": str(root / "project.durer"), "results": results}
    except Exception as exc:
        raise HTTPException(502, f"Could not open Dürer desktop: {exc}") from exc


@router.post("/api/native/dispatch")
def raw_dispatch(payload: ActionsRequest):
    """One-shot full native bridge; persistent editing should use the project endpoint."""
    try:
        return dispatch(payload.actions)
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc


from . import agent_tools
for _tool_name in ("illustration_list", "illustration_create", "illustration_inspect",
                   "illustration_native_call", "illustration_export", "vectorcraft_catalog"):
    router.add_api_route("/api/agent/" + _tool_name, getattr(agent_tools, _tool_name), methods=["POST"])
router.add_api_route("/api/agent/durer_catalog", agent_tools.vectorcraft_catalog, methods=["POST"])


def create_app(config):
    """Fresh native UI/API; the owner supplies paths before any request starts."""
    from .config import configure_owner
    from ....hoard_link import family, guard
    from ....hoard_link.tokens import read_or_create_token
    from ....hoard_link.copilot import install_copilot
    configure_owner(config)
    def shutdown():
        sessions.close()
        from .native import close_guis
        close_guis()
    @asynccontextmanager
    async def lifetime(app):
        await asyncio.to_thread(config.data_dir.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(read_or_create_token, config.data_dir/'mcp-token')
        try:
            yield
        finally:
            await asyncio.to_thread(shutdown)
    app = FastAPI(title='Daguerre · Vector',version='0.1.0',lifespan=lifetime)
    app.state.shutdown = shutdown
    app.include_router(router)
    app.mount('/static',StaticFiles(directory=ROOT/'durer_hoard'/'static'),name='static')
    family.install_fastapi(app,'durer',str(config.data_dir),contract=True,
        instructions='Owned vector projects, complete native tools and command registry. Activate explicitly.')
    # The SDK's event identity is process-wide. Both modules belong to this
    # owner; native contract closures still retain their own token directory.
    family.configure('daguerre',str(config.data_dir.parent))
    guard.install_guard(app,port_getter=lambda:config.port)
    install_copilot(app,'durer',str(config.data_dir),app_name="Daguerre's Hoard")
    return app

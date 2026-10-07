"""Local PhotoCraft and LightCraft MCP engines for Daguerre.

The adapters keep each engine's own MCP catalogue and schemas discoverable.
Every child runs in a Daguerre-owned workspace; registered photo roots are
read only and are copied into that workspace before an editing workflow.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ENGINES = ("photocraft", "lightcraft")
_APPDATA_KEYS = ("APPDATA", "LOCALAPPDATA")


class CraftEngineError(ValueError):
    """A safe, actionable engine configuration or invocation error."""


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _mcp_json(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        return {str(k): _mcp_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_mcp_json(v) for v in value]
    return value


class CraftEngines:
    """Discover, configure and call the two local Craft MCP servers."""

    def __init__(self, data_dir: Path, port: int = 8814):
        self.data_dir = data_dir.resolve()
        self.port = port
        self.config_path = self.data_dir / "craft-engines.json"
        self.workspace = self.data_dir / "craft-workspace"
        self.outputs = self.data_dir / "craft-outputs"
        self.runtime = self.data_dir / "craft-runtime"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.outputs.mkdir(parents=True, exist_ok=True)
        self.runtime.mkdir(parents=True, exist_ok=True)
        self._locks = {name: threading.Lock() for name in ENGINES}

    def _config(self) -> dict[str, str]:
        if not self.config_path.exists():
            return {}
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CraftEngineError(f"Cannot read {self.config_path}: {exc}") from None
        if not isinstance(data, dict) or set(data) - set(ENGINES):
            raise CraftEngineError(f"{self.config_path} must be a JSON object with only {', '.join(ENGINES)} paths")
        if any(not isinstance(value, str) for value in data.values()):
            raise CraftEngineError("Craft executable paths must be strings")
        return data

    def _bundle_dirs(self) -> list[Path]:
        dirs = [self.data_dir / "craft-apps", self.data_dir / "craft-bundles"]
        extra = os.environ.get("DAGUERRE_CRAFT_BUNDLES", "")
        dirs.extend(Path(p).expanduser() for p in extra.split(os.pathsep) if p.strip())
        return dirs

    def executable(self, engine: str) -> Path | None:
        if engine not in ENGINES:
            raise CraftEngineError(f"engine must be one of: {', '.join(ENGINES)}")
        config = self._config()
        configured = config.get(engine) or os.environ.get(f"DAGUERRE_{engine.upper()}_CLI")
        if configured:
            path = Path(configured).expanduser()
            if path.is_file():
                return path.resolve()
            return None
        cli_name = f"{engine}-cli.exe" if os.name == "nt" else f"{engine}-cli"
        found = shutil.which(cli_name)
        if found:
            return Path(found).resolve()
        for root in self._bundle_dirs():
            direct = root / cli_name
            if direct.is_file():
                return direct.resolve()
            if root.is_dir():
                for candidate in sorted(root.glob(f"*-windows-*-portable/{cli_name}")):
                    return candidate.resolve()
                for candidate in sorted(root.glob(f"*/{cli_name}")):
                    return candidate.resolve()
        return None

    def status(self) -> dict[str, Any]:
        engines = {}
        for name in ENGINES:
            exe = self.executable(name)
            engines[name] = {
                "available": exe is not None,
                "executable": str(exe) if exe else None,
                "configuration_file": str(self.config_path),
                "workspace": str(self.workspace),
                "capability": "full upstream MCP tools can be listed and called" if exe else "not configured",
            }
        return {"engines": engines, "outputs_dir": str(self.outputs)}

    def _server_params(self, engine: str) -> StdioServerParameters:
        exe = self.executable(engine)
        if exe is None:
            raise CraftEngineError(
                f"{engine} CLI not found. Configure it in {self.config_path}, "
                f"set DAGUERRE_{engine.upper()}_CLI, or put it under data/craft-apps."
            )
        env = dict(os.environ)
        for key in _APPDATA_KEYS:
            appdata = self.runtime / engine / key.lower()
            appdata.mkdir(parents=True, exist_ok=True)
            env[key] = str(appdata)
        if engine == "photocraft":
            args = [
                "mcp", "--automation-read-root", str(self.workspace),
                "--automation-write-root", str(self.workspace),
            ]
        else:
            library = self.runtime / "lightcraft-library"
            library.mkdir(parents=True, exist_ok=True)
            args = ["mcp", "--library", str(library)]
        return StdioServerParameters(command=str(exe), args=args, env=env, cwd=str(self.workspace))

    async def _request(self, engine: str, calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        with open(os.devnull, "w", encoding="utf-8") as errlog:
            async with stdio_client(self._server_params(engine), errlog=errlog) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await asyncio.wait_for(session.initialize(), timeout=45)
                    if calls and calls[0].get("tool") == "__list_tools__":
                        tools = await asyncio.wait_for(session.list_tools(), timeout=45)
                        return [{"tools": [_mcp_json(item) for item in tools.tools]}]
                    for call in calls:
                        result = await asyncio.wait_for(
                            session.call_tool(call["tool"], call.get("arguments", {})), timeout=120
                        )
                        results.append({"tool": call["tool"], "is_error": result.isError, "content": [_mcp_json(c) for c in result.content]})
                        if result.isError:
                            break
        return results

    def tools(self, engine: str) -> dict[str, Any]:
        self._validate_engine(engine)
        with self._locks[engine]:
            return asyncio.run(self._request(engine, [{"tool": "__list_tools__"}]))[0]

    @staticmethod
    def _validate_engine(engine: str) -> None:
        if engine not in ENGINES:
            raise CraftEngineError(f"engine must be one of: {', '.join(ENGINES)}")

    def _guard_arguments(self, engine: str, arguments: Any) -> None:
        """Confine path arguments to the disposable, app-owned workspace."""
        if engine == "photocraft":
            # PhotoCraft's own MCP server enforces explicit read/write roots.
            return
        def visit(value: Any, key: str = "") -> None:
            if isinstance(value, dict):
                for child_key, child in value.items():
                    visit(child, str(child_key).lower())
            elif isinstance(value, list):
                for child in value:
                    visit(child, key)
            elif isinstance(value, str):
                candidate = Path(value).expanduser()
                looks_like_path = any(part in key for part in ("path", "file", "folder", "dir"))
                if candidate.is_absolute():
                    if not (_inside(candidate, self.workspace) or _inside(candidate, self.outputs)):
                        raise CraftEngineError("LightCraft MCP file paths must stay inside Daguerre's isolated craft-workspace")
                elif looks_like_path:
                    if ".." in candidate.parts:
                        raise CraftEngineError("relative LightCraft paths cannot contain '..'")
                    if not _inside(self.workspace / candidate, self.workspace):
                        raise CraftEngineError("LightCraft MCP file paths must stay inside Daguerre's isolated craft-workspace")
        visit(arguments)

    def call(self, engine: str, calls: list[dict[str, Any]]) -> dict[str, Any]:
        self._validate_engine(engine)
        if not isinstance(calls, list) or not calls or len(calls) > 32:
            raise CraftEngineError("calls must contain 1 to 32 {tool, arguments} objects")
        clean: list[dict[str, Any]] = []
        for call in calls:
            if not isinstance(call, dict) or not isinstance(call.get("tool"), str) or call["tool"].startswith("__"):
                raise CraftEngineError("each call needs a public tool name and arguments object")
            arguments = call.get("arguments", {})
            if not isinstance(arguments, dict):
                raise CraftEngineError("tool arguments must be a JSON object")
            self._guard_arguments(engine, arguments)
            clean.append({"tool": call["tool"], "arguments": arguments})
        with self._locks[engine]:
            result = asyncio.run(self._request(engine, clean))
        return {"engine": engine, "calls": result, "workspace": str(self.workspace)}

    def create_layered_document(self, name: str, width: int, height: int, background: str, source: Path | None = None) -> dict[str, Any]:
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise CraftEngineError("name must contain 1 to 100 characters")
        if not 16 <= width <= 8192 or not 16 <= height <= 8192:
            raise CraftEngineError("width and height must be between 16 and 8192 pixels")
        if not isinstance(background, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", background):
            raise CraftEngineError("background must be a six-digit #RRGGBB color")
        artifact_id = uuid.uuid4().hex
        path = self.workspace / "exports" / f"{artifact_id}.pcraft"
        preview = self.workspace / "exports" / f"{artifact_id}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        native_rel = f"exports/{artifact_id}.pcraft"
        preview_rel = f"exports/{artifact_id}.png"
        calls = []
        if source is not None:
            if not source.is_file():
                raise CraftEngineError("source photo is missing")
            intake = self.workspace / "photocraft-input" / f"{artifact_id}{source.suffix.lower()}"
            intake.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, intake)
            relative = intake.relative_to(self.workspace).as_posix()
            calls.append({"tool": "doc_open", "arguments": {"path": relative}})
        else:
            calls.append({"tool": "doc_new", "arguments": {"name": name, "width": width, "height": height, "background": background}})
        calls.extend([
            {"tool": "command_run", "arguments": {"id": "layer.new.layer", "params": {"name": "Editable overlay"}}},
            {"tool": "doc_inspect", "arguments": {}},
            {"tool": "doc_save", "arguments": {"path": native_rel}},
            {"tool": "doc_export", "arguments": {"path": preview_rel, "format": "png"}},
        ])
        result = self.call("photocraft", calls)
        if len(result["calls"]) != len(calls) or any(x["is_error"] for x in result["calls"]):
            raise CraftEngineError("PhotoCraft did not complete document creation; inspect returned MCP call errors")
        if not path.is_file() or not preview.is_file():
            raise CraftEngineError("PhotoCraft reported success but the native document or PNG export is missing")
        return {"id": artifact_id, "engine": "photocraft", "native_path": str(path), "preview_path": str(preview), "preview_url": f"http://127.0.0.1:{self.port}/api/craft/artifacts/{artifact_id}.png", "native_format": ".pcraft", "editable_layers": True, "calls": result["calls"]}

    def create_layered_photo(self, source: Path) -> dict[str, Any]:
        """Open a disposable photo copy in PhotoCraft and save an editable project."""
        try:
            from PIL import Image
            with Image.open(source) as image:
                width, height = image.size
        except Exception as exc:
            raise CraftEngineError(f"PhotoCraft cannot read this image for a layered project: {exc}") from None
        return self.create_layered_document(source.stem[:100] or "Photo", width, height, "#000000", source)

    def develop_photo(self, source: Path, exposure: float, output_format: str = "png", long_edge: int = 0) -> dict[str, Any]:
        if not -5.0 <= exposure <= 5.0:
            raise CraftEngineError("exposure must be between -5 and 5 EV")
        if output_format.lower() not in {"png", "jpg", "tif", "webp", "avif"}:
            raise CraftEngineError("output_format must be png, jpg, tif, webp or avif")
        if not source.is_file():
            raise CraftEngineError("source photo is missing")
        artifact_id = uuid.uuid4().hex
        intake = self.workspace / "lightcraft-input" / f"{artifact_id}{source.suffix.lower()}"
        output = self.outputs / f"{artifact_id}.{output_format.lower()}"
        intake.parent.mkdir(parents=True, exist_ok=True)
        # Editing always begins from a copy. LightCraft only receives this copy,
        # and its persistent library is confined to Daguerre data/.
        shutil.copy2(source, intake)
        calls = [
            {"tool": "import", "arguments": {"paths": [str(intake)], "mode": "add"}},
            {"tool": "query_photos", "arguments": {}},
            {"tool": "get_develop", "arguments": {}},
            {"tool": "set_develop", "arguments": {"values": {"light.exposure": exposure}}},
            {"tool": "export", "arguments": {"path": str(output), "format": output_format.lower(), "colorSpace": "srgb", "metadata": "none", "longEdge": long_edge}},
            {"tool": "render_photo", "arguments": {"size": 512}},
        ]
        result = self.call("lightcraft", calls)
        if len(result["calls"]) != len(calls) or any(x["is_error"] for x in result["calls"]):
            raise CraftEngineError("LightCraft did not complete the develop/export workflow; inspect returned MCP call errors")
        if not output.is_file():
            raise CraftEngineError("LightCraft reported success but the exported image is missing")
        return {"id": artifact_id, "engine": "lightcraft", "source_copy": str(intake), "output_path": str(output), "output_url": f"http://127.0.0.1:{self.port}/api/craft/artifacts/{artifact_id}.{output_format.lower()}", "original_modified": False, "exposure_ev": exposure, "format": output_format.lower(), "calls": result["calls"]}

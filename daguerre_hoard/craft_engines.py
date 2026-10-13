"""Incorporated layered-image and development engines owned by Daguerre.

The adapters keep each engine's own MCP catalogue and schemas discoverable.
Every child runs in a Daguerre-owned workspace; registered photo roots are
read only and are copied into that workspace before an editing workflow.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import socket
import threading
import uuid
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from .hoard_link import proc
from .hoard_link.atomic import write_json_atomic


ENGINES = ("photocraft", "lightcraft")  # Historical public keys remain aliases.
ENGINE_NAMES = {"layers": "photocraft", "develop": "lightcraft", "photocraft": "photocraft", "lightcraft": "lightcraft"}
OWN_NAMES = {"photocraft": "layers", "lightcraft": "develop"}
ROOT = Path(__file__).resolve().parents[1]
_APPDATA_KEYS = ("APPDATA", "LOCALAPPDATA")


class CraftEngineError(ValueError):
    """A safe, actionable engine configuration or invocation error."""


class _EditorProcess:
    """A GUI that outlived its HTTP host; supports the same liveness check as Popen."""
    def __init__(self, pid: int):
        self.pid = pid

    def poll(self):
        return None if proc.pid_alive(self.pid) else 0


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
        self._editors: dict[str, Any] = {}
        self._editor_file = self.runtime / "editors.json"
        self._restore_editors()

    def _restore_editors(self) -> None:
        try:
            records = json.loads(self._editor_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(records, dict):
            return
        for name in ("layers", "develop"):
            record = records.get(name)
            if not isinstance(record, dict):
                continue
            binary = ROOT / "native/bin" / ("daguerre-" + name + (".exe" if os.name == "nt" else ""))
            pid, port = record.get("pid"), record.get("port")
            if record.get("binary") == str(binary) and isinstance(pid, int) and isinstance(port, int) and 0 < port < 65536 and proc.pid_alive(pid):
                self._editors[name] = {"process": _EditorProcess(pid), "port": port, "token_file": self.runtime / "layers-control-token"}

    def _save_editors(self) -> None:
        records = {}
        for name, editor in self._editors.items():
            if editor["process"].poll() is None:
                binary = ROOT / "native/bin" / ("daguerre-" + name + (".exe" if os.name == "nt" else ""))
                records[name] = {"pid": editor["process"].pid, "port": editor["port"], "binary": str(binary)}
        write_json_atomic(self._editor_file, records)

    def open_editor(self, artifact_id: str, engine: str) -> dict[str, Any]:
        """Open the incorporated full editor on a previously generated owned copy."""
        self._validate_engine(engine)
        engine = ENGINE_NAMES[engine]
        if not re.fullmatch(r"[0-9a-f]{32}", artifact_id):
            raise CraftEngineError("artifact_id must identify a generated Daguerre copy")
        name = OWN_NAMES[engine]
        gui = ROOT / "native/bin" / ("daguerre-" + name + (".exe" if os.name == "nt" else ""))
        if not gui.is_file():
            raise CraftEngineError("Daguerre editor is not installed")
        if name == "layers":
            path = self.workspace / "exports" / (artifact_id + ".dglayers")
            legacy = path.with_suffix(".pcraft")
            if not path.exists() and legacy.is_file():
                shutil.copy2(legacy, path)
            args = [str(gui), "--automation-read-root", str(self.workspace), "--automation-write-root", str(self.workspace), str(path)]
        else:
            copies = sorted((self.workspace / "lightcraft-input").glob(artifact_id + ".*"))
            if not copies:
                raise CraftEngineError("Generated development copy is missing")
            path = copies[0]
            self._server_params(engine)  # migrate/create the owned catalog before launching the editor
            args = [str(gui), "--library", str(self.runtime / "develop-library"), "--no-demo", str(path)]
        if not path.is_file():
            raise CraftEngineError("Generated editable copy is missing")
        key = name
        previous = self._editors.get(key)
        process = previous["process"] if previous else None
        if process is None or process.poll() is not None:
            params = self._server_params(engine)
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            args.extend(["--control", str(port)])
            token_file = self.runtime / "layers-control-token"
            if name == "layers":
                args.extend(["--control-token-file", str(token_file)])
            process = proc.popen(args, env=params.env, cwd=str(self.workspace), detached=True)
            self._editors[key] = {"process": process, "port": port, "token_file": token_file}
            self._save_editors()
        elif name == "layers":
            result = self.call("layers", [{"tool": "doc_open", "arguments": {"path": path.relative_to(self.workspace).as_posix()}}])
            if any(row["is_error"] for row in result["calls"]):
                raise CraftEngineError("The open layered editor could not load this copy")
        return {"engine": name, "artifact_id": artifact_id, "path": str(path), "executable": str(gui), "pid": process.pid, "original_modified": False}

    def executable(self, engine: str) -> Path | None:
        self._validate_engine(engine)
        canonical = ENGINE_NAMES[engine]
        filename = "daguerre-" + OWN_NAMES[canonical] + "-cli" + (".exe" if os.name == "nt" else "")
        path = ROOT / "native/bin" / filename
        return path if path.is_file() else None

    def status(self) -> dict[str, Any]:
        engines = {}
        for name in ENGINES:
            exe = self.executable(name)
            engines[name] = {
                "available": exe is not None,
                "executable": str(exe) if exe else None,
                "configuration_file": str(self.config_path),
                "workspace": str(self.workspace),
                "name": "Daguerre " + OWN_NAMES[name],
                "owned_engine": OWN_NAMES[name],
                "capability": "complete incorporated engine tools and editor" if exe else "not installed",
            }
        engines.update({OWN_NAMES[name]: value for name, value in list(engines.items())})
        return {"engines": engines, "outputs_dir": str(self.outputs), "source": "native"}

    def _server_params(self, engine: str) -> StdioServerParameters:
        self._validate_engine(engine)
        engine = ENGINE_NAMES[engine]
        exe = self.executable(engine)
        if exe is None:
            raise CraftEngineError(
                f"Daguerre {OWN_NAMES[engine]} engine is not installed from this repository."
            )
        env = dict(os.environ)
        for key in _APPDATA_KEYS:
            appdata = self.runtime / engine / key.lower()
            appdata.mkdir(parents=True, exist_ok=True)
            env[key] = str(appdata)
        if engine == "photocraft":
            config = self.runtime / "layers-config"
            historical = self.runtime / engine / "appdata" / "Photocraft"
            if not config.exists() and historical.is_dir():
                shutil.copytree(historical, config)
            config.mkdir(parents=True, exist_ok=True)
            env["DAGUERRE_LAYERS_CONFIG_DIR"] = str(config)
            args = [
                "mcp", "--automation-read-root", str(self.workspace),
                "--automation-write-root", str(self.workspace),
            ]
        else:
            old_preferences = self.runtime / engine / "appdata" / "LightCraft"
            own_preferences = self.runtime / engine / "appdata" / "Daguerre Develop"
            if not own_preferences.exists() and old_preferences.is_dir():
                shutil.copytree(old_preferences, own_preferences)
            library = self.runtime / "develop-library"
            historical = self.runtime / "lightcraft-library"
            if not library.exists() and historical.is_dir():
                shutil.copytree(historical, library)  # one-way import; historical bytes stay intact
            library.mkdir(parents=True, exist_ok=True)
            args = ["mcp", "--library", str(library)]
        editor = self._editors.get(OWN_NAMES[engine])
        if editor and editor["process"].poll() is None:
            address = f"127.0.0.1:{editor['port']}"
            if engine == "photocraft":
                args = ["mcp", "--bridge", address, "--control-token-file", str(editor["token_file"])]
            else:
                args = ["mcp", "--connect", address]
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
        engine = ENGINE_NAMES[engine]
        with self._locks[engine]:
            return asyncio.run(self._request(engine, [{"tool": "__list_tools__"}]))[0]

    @staticmethod
    def _validate_engine(engine: str) -> None:
        if engine not in ENGINE_NAMES:
            raise CraftEngineError("engine must be layers or develop (historical photocraft/lightcraft aliases accepted)")

    def _guard_arguments(self, engine: str, arguments: Any) -> None:
        """Confine path arguments to the disposable, app-owned workspace."""
        if engine == "photocraft":
            # Daguerre Layers's own MCP server enforces explicit read/write roots.
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
                        raise CraftEngineError("Daguerre Develop MCP file paths must stay inside Daguerre's isolated craft-workspace")
                elif looks_like_path:
                    if ".." in candidate.parts:
                        raise CraftEngineError("relative Daguerre Develop paths cannot contain '..'")
                    if not _inside(self.workspace / candidate, self.workspace):
                        raise CraftEngineError("Daguerre Develop MCP file paths must stay inside Daguerre's isolated craft-workspace")
        visit(arguments)

    def call(self, engine: str, calls: list[dict[str, Any]]) -> dict[str, Any]:
        self._validate_engine(engine)
        engine = ENGINE_NAMES[engine]
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
        return {"engine": OWN_NAMES[engine], "calls": result, "workspace": str(self.workspace)}

    def create_layered_document(self, name: str, width: int, height: int, background: str, source: Path | None = None) -> dict[str, Any]:
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise CraftEngineError("name must contain 1 to 100 characters")
        if not 16 <= width <= 8192 or not 16 <= height <= 8192:
            raise CraftEngineError("width and height must be between 16 and 8192 pixels")
        if not isinstance(background, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", background):
            raise CraftEngineError("background must be a six-digit #RRGGBB color")
        artifact_id = uuid.uuid4().hex
        path = self.workspace / "exports" / f"{artifact_id}.dglayers"
        preview = self.workspace / "exports" / f"{artifact_id}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        native_rel = f"exports/{artifact_id}.dglayers"
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
            raise CraftEngineError("Daguerre Layers did not complete document creation; inspect returned MCP call errors")
        if not path.is_file() or not preview.is_file():
            raise CraftEngineError("Daguerre Layers reported success but the native document or PNG export is missing")
        return {"id": artifact_id, "engine": "layers", "native_path": str(path), "preview_path": str(preview), "preview_url": f"http://127.0.0.1:{self.port}/api/craft/artifacts/{artifact_id}.png", "native_format": ".dglayers", "editable_layers": True, "calls": result["calls"]}

    def create_layered_photo(self, source: Path) -> dict[str, Any]:
        """Open a disposable photo copy in Daguerre Layers and save an editable project."""
        try:
            from PIL import Image
            with Image.open(source) as image:
                width, height = image.size
        except Exception as exc:
            raise CraftEngineError(f"Daguerre Layers cannot read this image for a layered project: {exc}") from None
        return self.create_layered_document(source.stem[:100] or "Photo", width, height, "#000000", source)

    def import_compositor(self, source_path: str, preflight_only: bool = False) -> dict[str, Any]:
        """Import a validated raster subset without flattening unsupported content."""
        from .compositor import preflight
        if not isinstance(source_path, str) or not source_path.strip():
            raise CraftEngineError("source_path must name an existing .comp directory")
        report, manifest, snapshot = preflight(Path(source_path).expanduser())
        report["preflight_only"] = preflight_only
        if preflight_only or report["status"] == "blocked":
            return report
        exe = self.executable("photocraft")
        if exe is None:
            raise CraftEngineError("Daguerre layered engine must be installed before importing")
        artifact_id = uuid.uuid4().hex
        intake = self.workspace / "compositor-input" / artifact_id / "original.comp"
        intake.mkdir(parents=True)
        for relative, data in snapshot.items():
            destination = intake / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        self.workspace.joinpath("exports").mkdir(exist_ok=True)
        native_rel, preview_rel = f"exports/{artifact_id}.dglayers", f"exports/{artifact_id}.png"
        native, preview = self.workspace / native_rel, self.workspace / preview_rel
        readback_rel = f"compositor-input/{artifact_id}/readback.png"
        readback = self.workspace / readback_rel
        def command(ident, params=None):
            return {"tool": "command_run", "arguments": {"id": ident, "params": params or {}}}
        calls = [command("file.new", {"name": Path(source_path).stem, "width": manifest["width"], "height": manifest["height"],
                                          "resolution": manifest.get("resolution", 72), "background": "transparent", "mode": "rgb", "depth": 8})]
        for index, layer in enumerate(manifest["layers"]):
            filename = layer.get("imageFile")
            if filename:
                relative = (intake / "images" / filename).relative_to(self.workspace).as_posix()
                calls.extend([{"tool": "doc_open", "arguments": {"path": relative}}, command("select.all"), command("edit.copy"),
                              {"tool": "doc_select", "arguments": {"index": 0}}, command("edit.pasteSpecial.pasteInPlace"),
                              {"tool": "doc_close", "arguments": {"index": 1}}])
            elif index > 0:
                calls.append(command("layer.new.layer"))
            calls.append(command("layer.setProps", {"name": layer["name"], "visible": layer["isVisible"], "opacity": layer.get("opacity", 1)}))
            if filename:
                x, y = layer["transform"]["origin"]
                calls.append(command("layer.translate", {"dx": int(x), "dy": int(y)}))
        calls.extend([{"tool": "doc_inspect", "arguments": {}}, {"tool": "doc_save", "arguments": {"path": native_rel}},
                      {"tool": "doc_export", "arguments": {"path": preview_rel, "format": "png"}}])
        def run_native(sequence):
            result = asyncio.run(self._request("photocraft", sequence))
            if len(result) != len(sequence) or any(c["is_error"] for c in result):
                raise CraftEngineError("Daguerre Layers import failed: " + json.dumps(result[-1] if result else {}))
            return result
        def payload(call):
            return json.loads(next(c["text"] for c in call["content"] if c.get("type") == "text"))
        report.update({"id": artifact_id, "source_copy": str(intake), "engine": "layers", "engine_executable": str(exe),
                       "engine_sha256": hashlib.sha256(exe.read_bytes()).hexdigest()})
        receipt = self.workspace / "exports" / f"{artifact_id}.json"
        try:
            with self._locks["photocraft"]:
                results = run_native(calls)
                state = payload(results[-3])
                native_layers = list(reversed(state["layers"]))
                # Remove the unused starter when the first source layer has pixels.
                cleanup = []
                if manifest["layers"][0].get("imageFile"):
                    starter = native_layers.pop(0)
                    cleanup.append(command("layer.delete", {"layer": starter["id"]}))
                if len(native_layers) != len(manifest["layers"]):
                    raise CraftEngineError("Daguerre Layers layer count differs from the source; import was not published")
                for layer_report, native_layer in zip(report["layers"], native_layers):
                    layer_report["native_id"] = native_layer["id"]
                readback_calls = [{"tool": "doc_open", "arguments": {"path": native_rel}}, *cleanup,
                                  {"tool": "doc_save", "arguments": {"path": native_rel}},
                                  {"tool": "doc_export", "arguments": {"path": preview_rel, "format": "png"}},
                                  {"tool": "doc_close", "arguments": {}}, {"tool": "doc_open", "arguments": {"path": native_rel}},
                                  {"tool": "doc_inspect", "arguments": {}},
                                  {"tool": "doc_export", "arguments": {"path": readback_rel, "format": "png"}}]
                reopened = run_native(readback_calls)
                readback_state = payload(reopened[-2])
                persisted = list(reversed(readback_state["layers"]))
                if len(persisted) != len(manifest["layers"]) or readback_state["width"] != manifest["width"] or readback_state["height"] != manifest["height"]:
                    raise CraftEngineError("Native readback has unexpected document dimensions or layer count")
                for source_layer, target in zip(manifest["layers"], persisted):
                    if target["name"] != source_layer["name"] or target["visible"] != source_layer["isVisible"] or abs(target["opacity"] - source_layer.get("opacity", 1)) > 0.000001 or target["blend"] != "Normal" or target["kind"] != "Pixel":
                        raise CraftEngineError("Native readback differs from imported layer properties")
                for layer_report, target in zip(report["layers"], persisted):
                    if target["bounds"] != layer_report["expected_native_bounds"]:
                        raise CraftEngineError("Native pixel bounds differ from the validated source placement")
                    layer_report["native_id"] = target["id"]
                if hashlib.sha256(preview.read_bytes()).digest() != hashlib.sha256(readback.read_bytes()).digest():
                    raise CraftEngineError("PNG export changed after native save/reopen")
            report.update({"status": "imported", "editable_layers": True, "native_path": str(native), "preview_path": str(preview),
                           "preview_url": f"http://127.0.0.1:{self.port}/api/craft/artifacts/{artifact_id}.png",
                           "native_url": f"http://127.0.0.1:{self.port}/api/craft/artifacts/{artifact_id}.dglayers",
                           "readback_path": str(readback), "readback": readback_state,
                           "native_sha256": hashlib.sha256(native.read_bytes()).hexdigest(),
                           "preview_sha256": hashlib.sha256(preview.read_bytes()).hexdigest(),
                           "readback_sha256": hashlib.sha256(readback.read_bytes()).hexdigest(),
                           "receipt_path": str(receipt), "receipt_url": f"http://127.0.0.1:{self.port}/api/craft/artifacts/{artifact_id}.json",
                           "native_calls": results + reopened})
            for layer in report["layers"]:
                for prop in layer["properties"]:
                    if prop["status"] == "supported":
                        prop["status"] = "mapped"
                        prop["reason"] = "Native pixel workflow completed; see readback evidence and renderer limitation"
        except Exception as exc:
            native.unlink(missing_ok=True)
            preview.unlink(missing_ok=True)
            report.update({"status": "failed", "error": str(exc), "receipt_path": str(receipt)})
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

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
        # Editing always begins from a copy. Daguerre Develop only receives this copy,
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
            raise CraftEngineError("Daguerre Develop did not complete the develop/export workflow; inspect returned MCP call errors")
        if not output.is_file():
            raise CraftEngineError("Daguerre Develop reported success but the exported image is missing")
        return {"id": artifact_id, "engine": "develop", "source_copy": str(intake), "output_path": str(output), "output_url": f"http://127.0.0.1:{self.port}/api/craft/artifacts/{artifact_id}.{output_format.lower()}", "original_modified": False, "exposure_ev": exposure, "format": output_format.lower(), "calls": result["calls"]}

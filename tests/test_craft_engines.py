from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from PIL import Image

from daguerre_hoard.craft_engines import CraftEngineError, CraftEngines


def test_portable_bundle_discovery_and_explicit_config(tmp_path, monkeypatch):
    bundle_root = tmp_path / "portable"
    photo = bundle_root / "photocraft-0.2.0-windows-x64-portable" / "photocraft-cli.exe"
    light = bundle_root / "lightcraft-0.2.1-windows-x64-portable" / "lightcraft-cli.exe"
    photo.parent.mkdir(parents=True)
    light.parent.mkdir(parents=True)
    photo.write_bytes(b"test executable")
    light.write_bytes(b"test executable")
    monkeypatch.setenv("DAGUERRE_CRAFT_BUNDLES", str(bundle_root))
    engines = CraftEngines(tmp_path / "data")
    if os.name == "nt":
        assert engines.executable("photocraft") == photo.resolve()
        assert engines.executable("lightcraft") == light.resolve()
    config_photo = tmp_path / "custom-photo-cli.exe"
    config_photo.write_bytes(b"configured executable")
    engines.config_path.write_text(json.dumps({"photocraft": str(config_photo)}), encoding="utf-8")
    assert engines.executable("photocraft") == config_photo.resolve()
    assert engines.executable("lightcraft") == light.resolve()


def test_lightcraft_file_arguments_are_confined_to_daguerre_owned_paths(tmp_path):
    engines = CraftEngines(tmp_path / "data")
    allowed = engines.workspace / "copy.png"
    blocked = tmp_path / "photo-root" / "original.png"
    allowed.parent.mkdir(parents=True, exist_ok=True)
    blocked.parent.mkdir(parents=True)
    allowed.touch()
    blocked.touch()
    engines._guard_arguments("lightcraft", {"paths": [str(allowed)]})
    engines._guard_arguments("lightcraft", {"path": str(engines.outputs / "render.png")})
    with pytest.raises(CraftEngineError, match="isolated craft-workspace"):
        engines._guard_arguments("lightcraft", {"paths": [str(blocked)]})
    with pytest.raises(CraftEngineError, match="cannot contain"):
        engines._guard_arguments("lightcraft", {"path": "../original.png"})


def test_photocraft_session_uses_enforced_read_write_roots(tmp_path):
    engines = CraftEngines(tmp_path / "data")
    cli = tmp_path / "photocraft-cli.exe"
    cli.write_bytes(b"fixture")
    engines.config_path.write_text(json.dumps({"photocraft": str(cli)}), encoding="utf-8")
    params = engines._server_params("photocraft")
    assert params.command == str(cli.resolve())
    assert params.args == ["mcp", "--automation-read-root", str(engines.workspace), "--automation-write-root", str(engines.workspace)]


def _configured_engines(tmp_path: Path) -> CraftEngines | None:
    root = os.environ.get("DAGUERRE_CRAFT_BUNDLES")
    if not root:
        pytest.skip("set DAGUERRE_CRAFT_BUNDLES to run real Craft artifact integration tests")
    engines = CraftEngines(tmp_path / "data")
    if not all(engines.executable(name) for name in ("photocraft", "lightcraft")):
        pytest.skip("both portable PhotoCraft and LightCraft CLI executables are required")
    return engines


@pytest.mark.craft_integration
def test_real_photocraft_saves_editable_layers_and_png(tmp_path):
    engines = _configured_engines(tmp_path)
    result = engines.create_layered_document("Reusable Hoard document", 160, 120, "#315c7e")
    native = Path(result["native_path"])
    preview = Path(result["preview_path"])
    assert native.is_file() and native.stat().st_size > 100
    with Image.open(preview) as image:
        assert image.size == (160, 120)
    inspect = next(c for c in result["calls"] if c["tool"] == "doc_inspect")
    state = json.loads(inspect["content"][0]["text"])
    names = {layer["name"] for layer in state["layers"]}
    assert {"Background", "Editable overlay"} <= names
    assert result["editable_layers"] is True


@pytest.mark.craft_integration
def test_real_photocraft_opens_a_copy_as_background_and_keeps_editable_overlay(tmp_path):
    engines = _configured_engines(tmp_path)
    source = tmp_path / "source" / "photo.png"
    source.parent.mkdir()
    Image.new("RGB", (96, 64), (40, 90, 130)).save(source)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    result = engines.create_layered_photo(source)
    assert Path(result["native_path"]).is_file()
    with Image.open(result["preview_path"]) as image:
        assert image.size == (96, 64)
        assert image.convert("RGB").getpixel((20, 20)) == (40, 90, 130)
    inspect = next(c for c in result["calls"] if c["tool"] == "doc_inspect")
    state = json.loads(inspect["content"][0]["text"])
    assert {layer["name"] for layer in state["layers"]} >= {"Background", "Editable overlay"}
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash


@pytest.mark.craft_integration
def test_real_lightcraft_exposure_exports_copy_and_preserves_original(tmp_path):
    engines = _configured_engines(tmp_path)
    source = tmp_path / "source" / "synthetic.png"
    source.parent.mkdir()
    Image.new("RGB", (192, 128), (49, 92, 126)).save(source)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    result = engines.develop_photo(source, 0.7, "png")
    exported = Path(result["output_path"])
    assert exported.is_file() and exported.stat().st_size > 100
    assert result["original_modified"] is False
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    assert Path(result["source_copy"]).is_file()
    assert any(call["tool"] == "set_develop" for call in result["calls"])
    with Image.open(source) as before, Image.open(exported) as after:
        assert after.size == before.size
        assert after.convert("RGB").getpixel((50, 50)) != before.getpixel((50, 50))

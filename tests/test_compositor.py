from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from PIL import Image

from daguerre_hoard.craft_engines import CraftEngines, CraftEngineError


def make_comp(path: Path, variant=0):
    """Synthetic, original multi-layer package following pinned Compositor v11."""
    (path / "images").mkdir(parents=True, exist_ok=True)
    records = []
    specs = [("Base", (64, 48), (0, 0), (20, 40, 160, 255), 1, True),
             ("Offset translucent overlay", (20, 15), (7 + variant, 9), (240, 20, 10, 255), 0.5, True),
             ("Hidden editable pixels", (8, 6), (-2, 3), (20, 250, 30, 180), 0.75, False)]
    for index, (name, size, origin, color, opacity, visible) in enumerate(specs):
        ident = f"00000000-0000-4000-8000-{index + 1:012d}"
        Image.new("RGBA", size, color).save(path / "images" / f"{ident}.png")
        records.append({"id": ident, "name": name, "isVisible": visible, "opacity": opacity, "blendMode": "Normal",
                        "imageFile": f"{ident}.png", "transform": {"origin": list(origin), "size": list(size),
                        "rotation": 0, "flipX": False, "flipY": False, "sampling": "High quality"}})
    manifest = {"format": "com.compositor.project", "version": 11, "colorSpace": "sRGB", "resolution": 144,
                "documentID": "11111111-1111-4111-8111-111111111111", "width": 64, "height": 48,
                "activeLayerID": records[1]["id"], "layers": records}
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def hashes(path):
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob("*") if p.is_file()}


def test_preflight_is_read_only_without_engine(tmp_path):
    source = tmp_path / "source.comp"
    make_comp(source)
    before = hashes(source)
    engines = CraftEngines(tmp_path / "data")
    result = engines.import_compositor(str(source), True)
    assert result["status"] == "ready" and len(result["layers"]) == 3
    assert result["files"] == before
    assert hashes(source) == before
    assert not list(engines.workspace.iterdir())


@pytest.mark.parametrize("change", ["group", "parent", "adjustment", "mask", "text", "shape", "effects", "blend", "rotation", "scale", "fraction", "missing", "corrupt", "path", "unknown", "version", "nan", "transparent"])
def test_unsupported_or_damaged_packages_block_before_writes(tmp_path, change):
    source = tmp_path / "blocked.comp"
    manifest = make_comp(source)
    layer = manifest["layers"][1]
    if change == "group": layer["isGroup"] = True
    elif change == "parent": layer["parentID"] = manifest["layers"][0]["id"]
    elif change == "adjustment": layer["adjustment"] = {"kind": "Exposure"}
    elif change == "mask": layer["maskFile"] = layer["id"] + ".mask.png"
    elif change == "text": layer["text"] = {"content": "Editable text"}
    elif change == "shape": layer["shape"] = {"kind": "Rectangle"}
    elif change == "effects": layer["effects"] = {"stroke": {"size": 5}}
    elif change == "blend": layer["blendMode"] = "Multiply"
    elif change == "rotation": layer["transform"]["rotation"] = 12
    elif change == "scale": layer["transform"]["size"][0] = 24
    elif change == "fraction": layer["transform"]["origin"][0] = 0.5
    elif change == "missing": (source / "images" / layer["imageFile"]).unlink()
    elif change == "corrupt": (source / "images" / layer["imageFile"]).write_bytes(b"invalid PNG")
    elif change == "path": layer["imageFile"] = "../outside.png"
    elif change == "unknown": layer["futureEffect"] = {"value": 1}
    elif change == "version": manifest["version"] = 12
    elif change == "nan": layer["opacity"] = float("nan")
    elif change == "transparent": Image.new("RGBA", (20, 15), (240, 20, 10, 0)).save(source / "images" / layer["imageFile"])
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    before = hashes(source)
    engines = CraftEngines(tmp_path / "data")
    engines._request = lambda *args: pytest.fail("blocked packages must never launch native engine")
    result = engines.import_compositor(str(source))
    assert result["status"] == "blocked"
    assert any(i["status"] == "blocking" for i in result["issues"]) or any(p["status"] == "blocking" for l in result["layers"] for p in l["properties"])
    assert hashes(source) == before
    assert not list(engines.workspace.iterdir())


def test_duplicate_json_fields_rejected(tmp_path):
    source = tmp_path / "bad.comp"
    source.mkdir()
    (source / "manifest.json").write_text('{"version":11,"version":1}', encoding="utf-8")
    with pytest.raises(CraftEngineError, match="Duplicate"):
        CraftEngines(tmp_path / "data").import_compositor(str(source), True)


def test_native_failure_retains_intake_receipt_and_source(tmp_path, monkeypatch):
    source = tmp_path / "source.comp"
    make_comp(source)
    before = hashes(source)
    engines = CraftEngines(tmp_path / "data")
    fake_executable = tmp_path / "native.exe"
    fake_executable.write_bytes(b"fake engine for failure testing")
    monkeypatch.setattr(engines, "executable", lambda engine: fake_executable)
    async def fail(*args):
        raise CraftEngineError("native engine failed")
    monkeypatch.setattr(engines, "_request", fail)
    result = engines.import_compositor(str(source))
    assert result["status"] == "failed" and "native engine failed" in result["error"]
    assert hashes(source) == before == hashes(Path(result["source_copy"]))
    assert Path(result["receipt_path"]).is_file()
    assert not list((engines.workspace / "exports").glob("*.pcraft"))
    assert not list((engines.workspace / "exports").glob("*.png"))


@pytest.mark.craft_integration
@pytest.mark.parametrize("variant", [0, 5])
def test_real_native_import_readback_layers_and_original_bytes(tmp_path, variant):
    if not os.environ.get("DAGUERRE_CRAFT_BUNDLES"):
        pytest.skip("configure native bundles for actual PhotoCraft integration")
    evidence = os.environ.get("DAGUERRE_COMPOSITOR_EVIDENCE")
    work = Path(evidence) / f"variant-{variant}" if evidence else tmp_path
    source = work / "source.comp"
    manifest = make_comp(source, variant)
    before = hashes(source)
    engines = CraftEngines(work / "data")
    result = engines.import_compositor(str(source))
    assert result["status"] == "imported", result
    assert hashes(source) == before == hashes(Path(result["source_copy"]))
    assert result["preview_sha256"] == result["readback_sha256"]
    assert result["readback"]["resolution"] == 144
    layers = list(reversed(result["readback"]["layers"]))
    assert [l["name"] for l in layers] == [l["name"] for l in manifest["layers"]]
    assert [l["opacity"] for l in layers] == [1, 0.5, 0.75]
    assert [l["visible"] for l in layers] == [True, True, False]
    assert layers[1]["bounds"] == [7 + variant, 9, 20, 15]
    assert layers[2]["bounds"] == [-2, 3, 8, 6]
    assert any(i["property"] == "activeLayerID" and i["status"] == "omitted" for i in result["issues"])
    with Image.open(result["preview_path"]) as image:
        assert image.size == (64, 48)
        assert image.convert("RGB").getpixel((1, 1)) == (20, 40, 160)
        pixel = image.convert("RGB").getpixel((10 + variant, 10))
        assert pixel == (130, 30, 85)  # 0.5 source-over, native 8-bit RGB rounding.
        assert image.convert("RGB").getpixel((6 + variant, 10)) == (20, 40, 160)
    # Reusable native editing: revealing a previously hidden layer changes export.
    edited = engines.call("photocraft", [
        {"tool": "doc_open", "arguments": {"path": Path(result["native_path"]).relative_to(engines.workspace).as_posix()}},
        {"tool": "command_run", "arguments": {"id": "layer.setProps", "params": {"layer": layers[2]["id"], "visible": True}}},
        {"tool": "doc_export", "arguments": {"path": "revealed.png", "format": "png"}},
    ])
    assert not any(call["is_error"] for call in edited["calls"])
    with Image.open(engines.workspace / "revealed.png") as image:
        assert image.convert("RGB").getpixel((1, 4)) != (20, 40, 160)


@pytest.mark.craft_integration
def test_real_transparent_margins_and_blank_layers_report_native_representation(tmp_path):
    if not os.environ.get("DAGUERRE_CRAFT_BUNDLES"):
        pytest.skip("configure native bundles for actual PhotoCraft integration")
    evidence = os.environ.get("DAGUERRE_COMPOSITOR_EVIDENCE")
    work = Path(evidence) / "transparent-and-blank" if evidence else tmp_path
    source = work / "source.comp"
    manifest = make_comp(source)
    image = Image.new("RGBA", (20, 15), (0, 0, 0, 0))
    image.paste((240, 20, 10, 128), (4, 3, 10, 8))
    image.save(source / "images" / manifest["layers"][1]["imageFile"])
    manifest["layers"][2].pop("imageFile")
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = CraftEngines(work / "data").import_compositor(str(source))
    assert result["status"] == "imported", result
    assert result["layers"][1]["expected_native_bounds"] == [11, 12, 6, 5]
    assert any(p["property"] == "transparent_pixel_extent" and p["status"] == "transformed" for p in result["layers"][1]["properties"])
    assert list(reversed(result["readback"]["layers"]))[2]["bounds"] == [0, 0, 0, 0]
    with Image.open(result["preview_path"]) as preview:
        assert preview.convert("RGB").getpixel((11, 12)) == (75, 35, 122)
        assert preview.convert("RGB").getpixel((10, 12)) == (20, 40, 160)

"""Strict, read-only Compositor package preflight. No renderer equivalence implied."""
from __future__ import annotations

import hashlib
import io
import json
import math
import uuid
from pathlib import Path

from PIL import Image

from .craft_engines import CraftEngineError

SOURCE_COMMIT = "11d8d7a50992b24fd9a760a1c13b1c01b70aaf30"
TOP_FIELDS = {"format", "version", "colorSpace", "resolution", "documentID", "width", "height", "activeLayerID", "layers", "guides"}
LAYER_FIELDS = {"id", "name", "isVisible", "transform", "imageFile", "parentID", "isGroup", "opacity", "blendMode", "maskFile", "maskEnabled", "maskSourceID", "adjustment", "maskPlacement", "maskLinked", "shape", "effects", "text"}
TRANSFORM_FIELDS = {"origin", "size", "rotation", "flipX", "flipY", "sampling"}


def _number(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def _uuid(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _read(path: Path, root: Path, maximum: int) -> bytes:
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        raise CraftEngineError(f"Missing or unsafe package asset: {path.name}")
    # Read through an open handle with a bound, including files replaced while reading.
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise CraftEngineError(f"Package asset exceeds {maximum} bytes: {path.name}")
    return data


def preflight(source: Path) -> tuple[dict, dict, dict[str, bytes]]:
    """Return an explicit report and immutable input snapshot; never write source."""
    if not source.is_dir() or source.suffix.lower() != ".comp" or source.is_symlink():
        raise CraftEngineError("source_path must be an existing .comp package directory")
    root = source.resolve()
    raw = _read(root / "manifest.json", root, 4 * 1024 * 1024)
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise CraftEngineError(f"Duplicate manifest key: {key}")
            result[key] = value
        return result
    try:
        manifest = json.loads(raw, object_pairs_hook=pairs)
    except (ValueError, UnicodeError) as exc:
        raise CraftEngineError(f"Invalid Compositor manifest: {exc}") from None
    if not isinstance(manifest, dict):
        raise CraftEngineError("manifest.json must contain an object")
    report = {"status": "ready", "source_path": str(root), "source_format": ".comp", "source_version": manifest.get("version"),
              "specification_commit": SOURCE_COMMIT, "original_modified": False, "issues": [
                  {"property": "documentID", "status": "transformed", "reason": "Source document UUID is retained in manifest provenance; PhotoCraft owns native document identity"},
                  {"property": "activeLayerID", "status": "omitted", "reason": "PhotoCraft reopens with its default selection; source selection remains in original manifest"}], "layers": [],
              "files": {"manifest.json": hashlib.sha256(raw).hexdigest()}, "limitations": [
                  "Only ungrouped 8-bit RGB/RGBA PNG pixel layers, Normal blending, native size, integer offsets, visibility and opacity are supported.",
                  "No Compositor renderer comparison; visual parity is unverified. No .comp export.",
                  "Source UUIDs become native IDs; the mapping is retained in the receipt. Undo history and viewport are not imported."]}
    def issue(property_name, reason, layer=None):
        item = {"property": property_name, "status": "blocking", "reason": reason}
        (layer["properties"] if layer else report["issues"]).append(item)
        report["status"] = "blocked"
    for key in sorted(set(manifest) - TOP_FIELDS):
        issue(key, "Unknown document field has no verified mapping")
    if manifest.get("format") != "com.compositor.project" or type(manifest.get("version")) is not int or not 1 <= manifest["version"] <= 11:
        issue("format/version", "Expected com.compositor.project, schema version 1–11")
    if manifest.get("colorSpace") != "sRGB":
        issue("colorSpace", "Only sRGB is supported")
    if not _uuid(manifest.get("documentID")):
        issue("documentID", "Expected a UUID")
    for key in ("width", "height"):
        if type(manifest.get(key)) is not int or not 1 <= manifest[key] <= 8192:
            issue(key, "Canvas sides must be integer pixels in 1–8192")
    if not _number(manifest.get("resolution", 72), 1, 9600):
        issue("resolution", "Resolution must be finite in 1–9600 ppi")
    if manifest.get("guides") not in (None, []):
        issue("guides", "Guide mapping is not verified")
    layers = manifest.get("layers")
    if not isinstance(layers, list) or not 1 <= len(layers) <= 128:
        issue("layers", "Expected 1–128 layers")
        return report, manifest, {"manifest.json": raw}
    snapshot = {"manifest.json": raw}
    ids, pixels, encoded = set(), 0, 0
    for index, record in enumerate(layers):
        layer = {"index_bottom_to_top": index, "source_id": record.get("id") if isinstance(record, dict) else None,
                 "name": record.get("name") if isinstance(record, dict) else None, "properties": []}
        report["layers"].append(layer)
        if not isinstance(record, dict):
            issue("layer", "Layer must be an object", layer)
            continue
        ident = _uuid(record.get("id"))
        if not ident or ident in ids:
            issue("id", "Expected a unique UUID", layer)
        ids.add(ident)
        if not isinstance(record.get("name"), str) or not record["name"].strip() or len(record["name"].encode("utf-8")) > 16384:
            issue("name", "Expected a nonempty name of at most 16384 UTF-8 bytes", layer)
        if type(record.get("isVisible")) is not bool:
            issue("isVisible", "Expected a boolean", layer)
        opacity = record.get("opacity", 1)
        if not _number(opacity, 0, 1) or (manifest.get("version", 0) in (1, 2) and opacity != 1):
            issue("opacity", "Expected finite 0–1 opacity; non-default values require schema v3+", layer)
        if record.get("blendMode", "Normal") != "Normal":
            issue("blendMode", "Only Normal blending has a verified mapping", layer)
        for key in sorted(set(record) - LAYER_FIELDS):
            issue(key, "Unknown layer field has no verified mapping", layer)
        if record.get("isGroup") is not None and record.get("isGroup") is not False:
            issue("isGroup", "Group semantics are not verified; groups are never flattened", layer)
        for key in ("parentID", "maskFile", "maskEnabled", "maskSourceID", "adjustment", "maskPlacement", "maskLinked", "shape", "effects", "text"):
            if record.get(key) is not None:
                issue(key, "Property has no verified editable mapping", layer)
        transform = record.get("transform")
        if not isinstance(transform, dict):
            issue("transform", "Expected a transform object", layer)
            transform = {}
        for key in sorted(set(transform) - TRANSFORM_FIELDS):
            issue("transform." + key, "Unknown transform field", layer)
        origin, size = transform.get("origin"), transform.get("size")
        if not isinstance(origin, list) or len(origin) != 2 or not all(_number(v, -1000000, 1000000) and float(v).is_integer() for v in origin):
            issue("transform.origin", "Only finite integer offsets within ±1000000 pixels are supported", layer)
        if not isinstance(size, list) or len(size) != 2 or not all(_number(v, 1, 8192) and float(v).is_integer() for v in size):
            issue("transform.size", "Expected integer native dimensions in 1–8192", layer)
        if transform.get("rotation") != 0 or type(transform.get("rotation")) not in (int, float) or transform.get("flipX") is not False or transform.get("flipY") is not False:
            issue("transform", "Only zero rotation and no flips are supported", layer)
        if transform.get("sampling") not in ("High quality", "Nearest neighbor"):
            issue("transform.sampling", "Expected High quality or Nearest neighbor; no resampling is performed", layer)
        filename = record.get("imageFile")
        if filename is not None:
            if not isinstance(filename, str) or not ident or filename.lower() != ident + ".png":
                issue("imageFile", "Asset must be named <layer UUID>.png without path components", layer)
            else:
                try:
                    data = _read(root / "images" / filename, root, 512 * 1024 * 1024)
                    encoded += len(data)
                    if encoded > 512 * 1024 * 1024:
                        raise CraftEngineError("Total encoded image budget exceeds 512 MiB")
                    with Image.open(io.BytesIO(data)) as image:
                        if image.format != "PNG" or len(data) < 25 or data[24] != 8 or image.mode not in ("RGB", "RGBA") or getattr(image, "n_frames", 1) != 1:
                            raise CraftEngineError("Expected a single-frame 8-bit RGB/RGBA PNG")
                        if "icc_profile" in image.info:
                            raise CraftEngineError("Embedded ICC profiles have no verified color mapping; use unprofiled sRGB RGB/RGBA PNG assets")
                        pixels += image.width * image.height
                        if max(image.size) > 8192 or pixels > 100000000:
                            raise CraftEngineError("Image side exceeds 8192 or total source pixels exceed 100 million")
                        if size != list(image.size):
                            issue("transform.size", "Scaled layers are unsupported; size must equal PNG dimensions", layer)
                        image.load()
                        bbox = image.getchannel("A").getbbox() if image.mode == "RGBA" else (0, 0, image.width, image.height)
                        if bbox is None:
                            issue("pixels", "Fully transparent PNG cannot be copied by the native engine; use a blank layer without imageFile", layer)
                        elif isinstance(origin, list) and len(origin) == 2 and all(_number(v, -1000000, 1000000) for v in origin):
                            layer["expected_native_bounds"] = [int(origin[0]) + bbox[0], int(origin[1]) + bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]]
                            if bbox != (0, 0, image.width, image.height):
                                layer["properties"].append({"property": "transparent_pixel_extent", "status": "transformed", "reason": "Native pixels trim fully transparent margins; placement of visible pixels is retained and original full PNG bytes are preserved"})
                    rel = "images/" + filename
                    snapshot[rel] = data
                    report["files"][rel] = hashlib.sha256(data).hexdigest()
                except (OSError, ValueError, Image.DecompressionBombError) as exc:
                    issue("imageFile", str(exc), layer)
        for property_name in ("name", "isVisible", "opacity", "blendMode", "transform.origin", "transform.size", "pixels", "order"):
            layer["properties"].append({"property": property_name, "status": "supported", "reason": "Imported only if entire preflight is ready"})
        if filename is None:
            layer["expected_native_bounds"] = [0, 0, 0, 0]
            layer["properties"].append({"property": "transform", "status": "transformed", "reason": "Blank layers become native empty pixel layers with no stored source rectangle; source transform remains in provenance"})
        layer["properties"].append({"property": "id", "status": "transformed", "reason": "Native numeric ID replaces source UUID; receipt records mapping"})
    active = manifest.get("activeLayerID")
    if active is not None and _uuid(active) not in ids:
        issue("activeLayerID", "Active layer must refer to an existing layer")
    return report, manifest, snapshot

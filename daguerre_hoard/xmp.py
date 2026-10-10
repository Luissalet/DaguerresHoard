"""XMP sidecars for Daguerre's retouch recipes (pure module: no database, no FastAPI).

A *recipe* is Daguerre's small, non-destructive develop description for one photo (exposure, tone sliders,
white balance, crop, orientation). This module maps it to and from the standard XMP that RAW developers keep
next to the image (``IMG_0001.CR3`` -> ``IMG_0001.xmp``):

* the settings that have a standard equivalent go to the Camera Raw settings namespace (``crs:``);
* rating, label and keywords go to ``xmp:Rating``, ``xmp:Label`` and ``dc:subject``;
* the complete recipe also goes, as JSON, to Daguerre's own ``daguerre:Recipe`` so nothing is lost on a round trip.

Writing never replaces a foreign sidecar: the existing document is parsed, only the properties Daguerre owns are
updated in place, and every other namespace, field and list is kept. Reading uses the standard library's expat parser
with doctype and entity declarations rejected (so no entity expansion and no network), a size cap and node/depth caps.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.parsers import expat

NS_X = "adobe:ns:meta/"
NS_RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
NS_XMP = "http://ns.adobe.com/xap/1.0/"
NS_DC = "http://purl.org/dc/elements/1.1/"
NS_CRS = "http://ns.adobe.com/camera-raw-settings/1.0/"
NS_TIFF = "http://ns.adobe.com/tiff/1.0/"
NS_XML = "http://www.w3.org/XML/1998/namespace"
NS_DAGUERRE = "https://github.com/Luissalet/DaguerresHoard/ns/1.0/"

PREFERRED_PREFIX = {
    NS_X: "x", NS_RDF: "rdf", NS_XMP: "xmp", NS_DC: "dc", NS_CRS: "crs", NS_TIFF: "tiff", NS_DAGUERRE: "daguerre",
}

MAX_XMP_BYTES = 2 * 1024 * 1024
MAX_NODES = 20_000
MAX_DEPTH = 40
MAX_IMPORTED_KEYS = 200
MAX_IMPORTED_VALUE_CHARS = 2000
RECIPE_VERSION = 1
CREATOR_TOOL = "Daguerre's Hoard"

# recipe key -> (crs property, minimum, maximum); all integer sliders
SLIDERS: dict[str, tuple[str, int, int]] = {
    "contrast": ("Contrast2012", -100, 100),
    "highlights": ("Highlights2012", -100, 100),
    "shadows": ("Shadows2012", -100, 100),
    "whites": ("Whites2012", -100, 100),
    "blacks": ("Blacks2012", -100, 100),
    "vibrance": ("Vibrance", -100, 100),
    "saturation": ("Saturation", -100, 100),
    "clarity": ("Clarity2012", -100, 100),
    "dehaze": ("Dehaze", -100, 100),
}
EXPOSURE_RANGE = (-5.0, 5.0)
TEMPERATURE_RANGE = (2000, 50000)
TINT_RANGE = (-150, 150)
ANGLE_RANGE = (-45.0, 45.0)
CROP_EDGES = ("left", "top", "right", "bottom")
RECIPE_KEYS = ("exposure", *SLIDERS, "temperature", "tint", "crop", "orientation")

# crs properties that describe the file's structure, not a setting: never reported as "imported, not applied"
_STRUCTURAL_CRS = {"Version", "ProcessVersion", "HasSettings", "WhiteBalance", "HasCrop", "CropConstrainToWarp",
                   "AlreadyApplied", "RawFileName"}
_CROP_CRS = {"left": "CropLeft", "top": "CropTop", "right": "CropRight", "bottom": "CropBottom"}


class XmpError(ValueError):
    """A recipe or an XMP document that Daguerre cannot accept; the message says what is wrong."""


# --------------------------------------------------------------------------- #
# Recipe model
# --------------------------------------------------------------------------- #
def _num(name: str, value: Any) -> float:
    if isinstance(value, bool):
        raise XmpError(f"{name} must be a number, got {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise XmpError(f"{name} must be a number, got {value!r}") from None
    if number != number or number in (float("inf"), float("-inf")):
        raise XmpError(f"{name} must be a finite number, got {value!r}")
    return number


def _in_range(name: str, number: float, low: float, high: float) -> float:
    if not low <= number <= high:
        raise XmpError(f"{name} must be between {low:g} and {high:g}, got {number:g}")
    return number


def accepted_recipe_keys() -> str:
    return ", ".join(RECIPE_KEYS)


def validate_recipe_patch(raw: Any) -> dict[str, Any]:
    """Validate a (possibly partial) recipe. A value of ``None`` means "clear this setting" and is kept as None."""
    if not isinstance(raw, dict):
        raise XmpError("recipe must be an object such as {\"exposure\": 0.5, \"contrast\": 10}")
    unknown = sorted(set(raw) - set(RECIPE_KEYS))
    if unknown:
        raise XmpError(f"unknown recipe field(s): {', '.join(unknown)}. Accepted: {accepted_recipe_keys()}")
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if value is None:
            out[key] = None
        elif key == "exposure":
            out[key] = round(_in_range("exposure", _num(key, value), *EXPOSURE_RANGE), 2)
        elif key in SLIDERS:
            _, low, high = SLIDERS[key]
            out[key] = int(round(_in_range(key, _num(key, value), low, high)))
        elif key == "temperature":
            out[key] = int(round(_in_range("temperature", _num(key, value), *TEMPERATURE_RANGE)))
        elif key == "tint":
            out[key] = int(round(_in_range("tint", _num(key, value), *TINT_RANGE)))
        elif key == "orientation":
            number = _num(key, value)
            if number != int(number) or not 1 <= number <= 8:
                raise XmpError(f"orientation must be an EXIF orientation from 1 to 8, got {value!r}")
            out[key] = int(number)
        else:  # crop
            out[key] = _validate_crop(value)
    return out


def _validate_crop(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        raise XmpError("crop must be an object such as {\"left\": 0.1, \"top\": 0.1, \"right\": 0.9, \"bottom\": 0.9, \"angle\": 0}")
    unknown = sorted(set(value) - {*CROP_EDGES, "angle"})
    if unknown:
        raise XmpError(f"unknown crop field(s): {', '.join(unknown)}. Accepted: left, top, right, bottom, angle")
    crop = {"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 1.0, "angle": 0.0}
    for key, item in value.items():
        if item is None:
            continue
        number = _num(f"crop.{key}", item)
        low, high = ANGLE_RANGE if key == "angle" else (0.0, 1.0)
        crop[key] = round(_in_range(f"crop.{key}", number, low, high), 6)
    if crop["right"] <= crop["left"] or crop["bottom"] <= crop["top"]:
        raise XmpError("crop needs right > left and bottom > top (edges are fractions of the image, 0 to 1)")
    return crop


def merge_recipe(current: dict[str, Any] | None, patch: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Apply a validated patch to a recipe. Returns the new recipe and the keys the patch cleared."""
    recipe = dict(current or {})
    cleared: list[str] = []
    for key, value in patch.items():
        if value is None:
            recipe.pop(key, None)
            cleared.append(key)
        else:
            recipe[key] = value
    return recipe, cleared


def recipe_to_crs(recipe: dict[str, Any]) -> dict[str, str]:
    """The standard ``crs:`` properties for a recipe (strings, formatted like RAW developers write them)."""
    crs: dict[str, str] = {}
    if "exposure" in recipe:
        crs["Exposure2012"] = f"{float(recipe['exposure']):+.2f}"
    for key, (name, _, _) in SLIDERS.items():
        if key in recipe:
            crs[name] = f"{int(recipe[key]):+d}"
    if "temperature" in recipe:
        crs["Temperature"] = str(int(recipe["temperature"]))
    if "tint" in recipe:
        crs["Tint"] = f"{int(recipe['tint']):+d}"
    if "temperature" in recipe or "tint" in recipe:
        crs["WhiteBalance"] = "Custom"
    crop = recipe.get("crop")
    if crop:
        for edge, name in _CROP_CRS.items():
            crs[name] = f"{float(crop.get(edge, 0.0 if edge in ('left', 'top') else 1.0)):.6f}"
        crs["CropAngle"] = f"{float(crop.get('angle', 0.0)):.6f}"
        crs["HasCrop"] = "True"
    return crs


def crs_names_for(keys: list[str]) -> list[str]:
    """The ``crs:`` properties that belong to these recipe keys (used to remove cleared settings)."""
    names: list[str] = []
    for key in keys:
        if key == "exposure":
            names.append("Exposure2012")
        elif key in SLIDERS:
            names.append(SLIDERS[key][0])
        elif key == "temperature":
            names.append("Temperature")
        elif key == "tint":
            names.append("Tint")
        elif key == "crop":
            names += [*_CROP_CRS.values(), "CropAngle", "HasCrop"]
    return names


def _crs_float(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        number = float(value.strip())
    except ValueError:
        return None
    return number if number == number and abs(number) != float("inf") else None


def crs_to_recipe(crs: dict[str, Any], exif_orientation: int | None = None,
                  orientation: int | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Map ``crs:`` values back into a recipe. Returns ``(recipe, unmapped)``: ``unmapped`` holds every other
    ``crs:`` setting (tone curves, HSL, sharpening, masks...) and any value outside Daguerre's ranges, which
    stay in the sidecar untouched but are not applied by Daguerre."""
    recipe: dict[str, Any] = {}
    used: set[str] = set()

    def take(prop: str, low: float, high: float) -> float | None:
        number = _crs_float(crs.get(prop))
        if number is None:
            return None
        if not low <= number <= high:
            return None
        used.add(prop)
        return number

    number = take("Exposure2012", *EXPOSURE_RANGE)
    if number is not None:
        recipe["exposure"] = round(number, 2)
    for key, (name, low, high) in SLIDERS.items():
        number = take(name, low, high)
        if number is not None:
            recipe[key] = int(round(number))
    number = take("Temperature", *TEMPERATURE_RANGE)
    if number is not None:
        recipe["temperature"] = int(round(number))
    number = take("Tint", *TINT_RANGE)
    if number is not None:
        recipe["tint"] = int(round(number))
    has_crop = str(crs.get("HasCrop", "")).strip().lower()
    if has_crop != "false" and any(name in crs for name in _CROP_CRS.values()):
        crop = {"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 1.0, "angle": 0.0}
        ok = True
        for edge, name in _CROP_CRS.items():
            value = take(name, 0.0, 1.0)
            if name in crs and value is None:
                ok = False
            elif value is not None:
                crop[edge] = round(value, 6)
        angle = take("CropAngle", *ANGLE_RANGE)
        if "CropAngle" in crs and angle is None:
            ok = False
        elif angle is not None:
            crop["angle"] = round(angle, 6)
        if ok and crop["right"] > crop["left"] and crop["bottom"] > crop["top"]:
            recipe["crop"] = crop
        else:
            used -= {*_CROP_CRS.values(), "CropAngle"}
    if orientation is not None and orientation != exif_orientation and 1 <= orientation <= 8:
        recipe["orientation"] = orientation
    unmapped = {k: v for k, v in crs.items() if k not in used and k not in _STRUCTURAL_CRS}
    return recipe, unmapped


def limit_imported(values: dict[str, Any]) -> dict[str, Any]:
    """Cap what is stored as "imported, not applied": a few hundred keys, values of bounded size."""
    out: dict[str, Any] = {}
    for key, value in list(values.items())[:MAX_IMPORTED_KEYS]:
        text = json.dumps(value, ensure_ascii=False)
        out[key] = value if len(text) <= MAX_IMPORTED_VALUE_CHARS else text[:MAX_IMPORTED_VALUE_CHARS] + "..."
    return out


# --------------------------------------------------------------------------- #
# Safe XML tree (keeps namespace prefixes so a foreign sidecar survives a merge)
# --------------------------------------------------------------------------- #
class _Node:
    __slots__ = ("tag", "attrib", "text", "tail", "children", "nsdecls")

    def __init__(self, tag: str, attrib: dict[str, str] | None = None, nsdecls: list[tuple[str, str]] | None = None):
        self.tag = tag
        self.attrib = attrib if attrib is not None else {}
        self.text: str | None = None
        self.tail: str | None = None
        self.children: list[_Node] = []
        self.nsdecls: list[tuple[str, str]] = nsdecls or []


def q(uri: str, local: str) -> str:
    return f"{{{uri}}}{local}"


def _split(tag: str) -> tuple[str | None, str]:
    if tag.startswith("{"):
        uri, _, local = tag[1:].partition("}")
        return uri, local
    return None, tag


class _Builder:
    """Builds a _Node tree from expat events and remembers where each prefix was declared."""

    def __init__(self) -> None:
        self.root: _Node | None = None
        self.stack: list[_Node] = []
        self._pending: list[tuple[str, str]] = []
        self.count = 0

    @staticmethod
    def _clark(name: str) -> str:
        uri, sep, local = name.partition("}")
        return f"{{{uri}}}{local}" if sep else name

    def start_ns(self, prefix: str | None, uri: str) -> None:
        self._pending.append((prefix or "", uri))

    def start(self, name: str, attrib: dict[str, str]) -> None:
        self.count += 1
        if self.count > MAX_NODES or len(self.stack) >= MAX_DEPTH:
            raise XmpError("XMP document is too large or too deeply nested")
        node = _Node(self._clark(name), {self._clark(k): v for k, v in attrib.items()}, self._pending)
        self._pending = []
        if self.stack:
            self.stack[-1].children.append(node)
        elif self.root is None:
            self.root = node
        self.stack.append(node)

    def end(self, name: str) -> None:
        self.stack.pop()

    def data(self, text: str) -> None:
        if not self.stack:
            return
        parent = self.stack[-1]
        if parent.children:
            last = parent.children[-1]
            last.tail = (last.tail or "") + text
        else:
            parent.text = (parent.text or "") + text


def _reject(*_args: Any) -> None:
    raise XmpError("XMP with a DOCTYPE or entity declarations is refused (entity expansion is not allowed)")


def parse_xmp(data: bytes) -> _Node:
    """Parse an XMP document safely. Raises XmpError for anything that is not a plain XML/RDF document."""
    if not isinstance(data, (bytes, bytearray)):
        raise XmpError("XMP data must be bytes")
    if len(data) > MAX_XMP_BYTES:
        raise XmpError(f"XMP document is larger than {MAX_XMP_BYTES // (1024 * 1024)} MB")
    builder = _Builder()
    parser = expat.ParserCreate(namespace_separator="}")
    parser.buffer_text = True
    parser.StartNamespaceDeclHandler = builder.start_ns
    parser.StartElementHandler = builder.start
    parser.EndElementHandler = builder.end
    parser.CharacterDataHandler = builder.data
    # No DTDs, entities or external entities: nothing to expand, nothing to fetch.
    parser.StartDoctypeDeclHandler = _reject
    parser.EntityDeclHandler = _reject
    parser.NotationDeclHandler = _reject
    parser.ExternalEntityRefHandler = _reject
    try:
        parser.Parse(bytes(data), True)
    except XmpError:
        raise
    except expat.ExpatError as exc:
        raise XmpError(f"not valid XML: {exc}") from None
    if builder.root is None:
        raise XmpError("empty XML document")
    return builder.root


def _find_rdf(root: _Node) -> _Node:
    stack = [root]
    while stack:
        node = stack.pop(0)
        if node.tag == q(NS_RDF, "RDF"):
            return node
        stack.extend(node.children)
    raise XmpError("no rdf:RDF element: this is not an XMP packet")


def _descriptions(rdf: _Node) -> list[_Node]:
    return [c for c in rdf.children if c.tag == q(NS_RDF, "Description")]


def _value_of(node: _Node) -> Any:
    containers = [c for c in node.children if _split(c.tag)[0] == NS_RDF and _split(c.tag)[1] in ("Seq", "Bag", "Alt")]
    if containers:
        return [_value_of(li) for li in containers[0].children if li.tag == q(NS_RDF, "li")]
    if node.children:
        return {_split(c.tag)[1]: _value_of(c) for c in node.children}
    return (node.text or "").strip()


def _props(rdf: _Node, uri: str) -> dict[str, Any]:
    """Every property in one namespace, whether written as an attribute or as an element."""
    out: dict[str, Any] = {}
    for desc in _descriptions(rdf):
        for key, value in desc.attrib.items():
            ns, local = _split(key)
            if ns == uri:
                out[local] = value
        for child in desc.children:
            ns, local = _split(child.tag)
            if ns == uri:
                out[local] = _value_of(child)
    return out


@dataclass
class XmpInfo:
    """What Daguerre understands in an XMP document."""

    rating: int | None = None
    label: str | None = None
    keywords: list[str] | None = None
    orientation: int | None = None
    crs: dict[str, Any] = field(default_factory=dict)
    daguerre_recipe: dict[str, Any] | None = None
    daguerre_version: int | None = None

    @property
    def written_by_daguerre(self) -> bool:
        return self.daguerre_version is not None


def read_xmp(data: bytes) -> XmpInfo:
    rdf = _find_rdf(parse_xmp(data))
    xmp, dc, tiff, crs, dag = (_props(rdf, ns) for ns in (NS_XMP, NS_DC, NS_TIFF, NS_CRS, NS_DAGUERRE))
    info = XmpInfo(crs=crs)
    rating = xmp.get("Rating")
    if isinstance(rating, str):
        number = _crs_float(rating)
        if number is not None and -1 <= number <= 5:
            info.rating = int(round(number))
    label = xmp.get("Label")
    if isinstance(label, str) and label.strip():
        info.label = label.strip()[:64]
    subject = dc.get("subject")
    if isinstance(subject, list):
        info.keywords = _clean_keywords([s for s in subject if isinstance(s, str)])
    elif isinstance(subject, str) and subject.strip():
        info.keywords = _clean_keywords([subject])
    orientation = _crs_float(tiff.get("Orientation"))
    if orientation is not None and orientation == int(orientation) and 1 <= orientation <= 8:
        info.orientation = int(orientation)
    raw = dag.get("Recipe")
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            info.daguerre_recipe = validate_recipe_patch(parsed) if isinstance(parsed, dict) else None
            if info.daguerre_recipe is not None:
                info.daguerre_recipe = {k: v for k, v in info.daguerre_recipe.items() if v is not None}
        except (ValueError, XmpError):
            info.daguerre_recipe = None  # a hand-edited, broken daguerre:Recipe falls back to the crs: values
    version = _crs_float(dag.get("Version"))
    if version is not None:
        info.daguerre_version = int(version)
    return info


def _clean_keywords(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        word = " ".join(str(value).split())[:100]
        if word and word.casefold() not in seen:
            seen.add(word.casefold())
            out.append(word)
        if len(out) >= 200:
            break
    return out


clean_keywords = _clean_keywords


# --------------------------------------------------------------------------- #
# Merge: update only what Daguerre owns
# --------------------------------------------------------------------------- #
@dataclass
class SidecarEdits:
    """What Daguerre writes. ``None`` means "leave whatever the file has"."""

    recipe: dict[str, Any] = field(default_factory=dict)
    cleared: list[str] = field(default_factory=list)
    rating: int | None = None
    label: str | None = None  # "" removes xmp:Label
    keywords: list[str] | None = None  # [] removes dc:subject
    when: str | None = None


def _new_description() -> _Node:
    desc = _Node(q(NS_RDF, "Description"), {q(NS_RDF, "about"): ""})
    desc.nsdecls = [("xmp", NS_XMP), ("dc", NS_DC), ("crs", NS_CRS), ("daguerre", NS_DAGUERRE)]
    return desc


def _new_document() -> _Node:
    root = _Node(q(NS_X, "xmpmeta"), {q(NS_X, "xmptk"): CREATOR_TOOL}, [("x", NS_X)])
    rdf = _Node(q(NS_RDF, "RDF"), nsdecls=[("rdf", NS_RDF)])
    rdf.children.append(_new_description())
    root.children.append(rdf)
    return root


def _find_prop(rdf: _Node, uri: str, local: str) -> tuple[_Node, str, _Node | None] | None:
    key = q(uri, local)
    for desc in _descriptions(rdf):
        if key in desc.attrib:
            return desc, "attr", None
        for child in desc.children:
            if child.tag == key:
                return desc, "elem", child
    return None


def _remove_prop(rdf: _Node, uri: str, local: str) -> None:
    key = q(uri, local)
    for desc in _descriptions(rdf):
        desc.attrib.pop(key, None)
        desc.children = [c for c in desc.children if c.tag != key]


def _set_simple(rdf: _Node, uri: str, local: str, value: str, *, as_element: bool = False) -> None:
    found = _find_prop(rdf, uri, local)
    if found:
        desc, kind, child = found
        if kind == "attr" and not as_element:
            desc.attrib[q(uri, local)] = value
            return
        _remove_prop(rdf, uri, local)
    desc = _descriptions(rdf)[0]
    if as_element:
        node = _Node(q(uri, local))
        node.text = value
        desc.children.append(node)
    else:
        desc.attrib[q(uri, local)] = value


def _set_bag(rdf: _Node, uri: str, local: str, values: list[str]) -> None:
    found = _find_prop(rdf, uri, local)
    kind = "Bag"
    if found and found[1] == "elem" and found[2] is not None:
        for c in found[2].children:
            ns, name = _split(c.tag)
            if ns == NS_RDF and name in ("Seq", "Bag"):
                kind = name
                break
    _remove_prop(rdf, uri, local)
    if not values:
        return
    holder = _Node(q(uri, local))
    container = _Node(q(NS_RDF, kind))
    for value in values:
        li = _Node(q(NS_RDF, "li"))
        li.text = value
        container.children.append(li)
    holder.children.append(container)
    _descriptions(rdf)[0].children.append(holder)


def _has_text(node: _Node) -> bool:
    return bool((node.text or "").strip()) or any((c.tail or "").strip() for c in node.children)


def _reindent(node: _Node, level: int = 0, unit: str = "   ") -> None:
    if node.children and not _has_text(node):
        inner = "\n" + unit * (level + 1)
        node.text = inner
        for i, child in enumerate(node.children):
            child.tail = inner if i < len(node.children) - 1 else "\n" + unit * level
    for child in node.children:
        _reindent(child, level + 1, unit)


class _Scope:
    def __init__(self, parent: "_Scope | None" = None) -> None:
        self.parent = parent
        self.map: dict[str, str] = {}

    def resolve(self, prefix: str) -> str | None:
        scope: _Scope | None = self
        while scope:
            if prefix in scope.map:
                return scope.map[prefix]
            scope = scope.parent
        return None

    def prefix_of(self, uri: str, allow_default: bool) -> str | None:
        scope: _Scope | None = self
        while scope:
            for prefix, bound in scope.map.items():
                if bound == uri and (prefix or allow_default) and self.resolve(prefix) == uri:
                    return prefix
            scope = scope.parent
        return None


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_attr(text: str) -> str:
    return (_esc(text).replace('"', "&quot;").replace("\r", "&#13;").replace("\n", "&#10;").replace("\t", "&#9;"))


def _emit(node: _Node, parent: _Scope | None, out: list[str], level: int, counter: list[int]) -> None:
    scope = _Scope(parent)
    decls: list[tuple[str, str]] = []
    for prefix, uri in node.nsdecls:
        scope.map[prefix] = uri
        decls.append((prefix, uri))

    def name_for(tag: str, attribute: bool) -> str:
        uri, local = _split(tag)
        if uri is None:
            return local
        if uri == NS_XML:
            return f"xml:{local}"
        prefix = scope.prefix_of(uri, allow_default=not attribute)
        if prefix is None:
            prefix = PREFERRED_PREFIX.get(uri) or ""
            while not prefix or scope.resolve(prefix) not in (None, uri):
                counter[0] += 1
                prefix = (PREFERRED_PREFIX.get(uri) or "ns") + str(counter[0])
            scope.map[prefix] = uri
            decls.append((prefix, uri))
        return f"{prefix}:{local}" if prefix else local

    tag_name = name_for(node.tag, False)
    attrs = [(name_for(key, True), value) for key, value in node.attrib.items()]
    parts = [f'xmlns{":" + p if p else ""}="{_esc_attr(u)}"' for p, u in decls]
    parts += [f'{k}="{_esc_attr(v)}"' for k, v in attrs]
    pad = "   " * (level + 1)
    if len(parts) > 3:
        head = f"<{tag_name}" + "".join(f"\n{pad}{p}" for p in parts)
    else:
        head = f"<{tag_name}" + "".join(f" {p}" for p in parts)
    if not node.children and not (node.text or ""):
        out.append(head + "/>")
        return
    out.append(head + ">")
    if node.text:
        out.append(_esc(node.text))
    for child in node.children:
        _emit(child, scope, out, level + 1, counter)
        if child.tail:
            out.append(_esc(child.tail))
    out.append(f"</{tag_name}>")


def serialize(root: _Node) -> bytes:
    body: list[str] = []
    _emit(root, None, body, 0, [0])
    text = ('<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n' + "".join(body)
            + '\n<?xpacket end="w"?>\n')
    return text.encode("utf-8")


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def merge_sidecar(existing: bytes | None, edits: SidecarEdits) -> bytes:
    """The sidecar bytes after applying ``edits`` to ``existing`` (or to a new document when there is none).

    Only Daguerre's properties are touched: the recipe's ``crs:`` equivalents, ``xmp:Rating`` / ``xmp:Label`` /
    ``dc:subject`` when given, ``tiff:Orientation`` when the recipe sets one, and ``daguerre:*``. Everything else
    (other namespaces, the rest of ``crs:``, structured values, history) stays exactly as it was."""
    root = parse_xmp(existing) if existing else _new_document()
    rdf = _find_rdf(root)
    if not _descriptions(rdf):
        rdf.children.append(_new_description())
    stamp = edits.when or _utc_now()
    crs = recipe_to_crs(edits.recipe)
    for name in crs_names_for(edits.cleared):
        if name not in crs:
            _remove_prop(rdf, NS_CRS, name)
    for name, value in crs.items():
        _set_simple(rdf, NS_CRS, name, value)
    if crs:
        for name, value in (("Version", "15.0"), ("ProcessVersion", "11.0"), ("HasSettings", "True")):
            if not _find_prop(rdf, NS_CRS, name):
                _set_simple(rdf, NS_CRS, name, value)
    if "orientation" in edits.recipe:
        _set_simple(rdf, NS_TIFF, "Orientation", str(int(edits.recipe["orientation"])))
    elif "orientation" in edits.cleared:
        _remove_prop(rdf, NS_TIFF, "Orientation")
    if edits.rating is not None:
        _set_simple(rdf, NS_XMP, "Rating", str(int(edits.rating)))
    if edits.label is not None:
        if edits.label:
            _set_simple(rdf, NS_XMP, "Label", edits.label)
        else:
            _remove_prop(rdf, NS_XMP, "Label")
    if edits.keywords is not None:
        _set_bag(rdf, NS_DC, "subject", edits.keywords)
    if not _find_prop(rdf, NS_XMP, "CreatorTool"):
        _set_simple(rdf, NS_XMP, "CreatorTool", CREATOR_TOOL)
    _set_simple(rdf, NS_XMP, "MetadataDate", stamp)
    _set_simple(rdf, NS_DAGUERRE, "Version", str(RECIPE_VERSION))
    _set_simple(rdf, NS_DAGUERRE, "RecipeUpdated", stamp)
    _set_simple(rdf, NS_DAGUERRE, "Recipe", json.dumps(edits.recipe, ensure_ascii=False, separators=(",", ":"),
                                                      sort_keys=True), as_element=True)
    _reindent(root)
    return serialize(root)


# --------------------------------------------------------------------------- #
# Where sidecars live, and XMP embedded in the image itself
# --------------------------------------------------------------------------- #
def sidecar_candidates(photo: Path) -> list[Path]:
    """``IMG_0001.xmp`` (the RAW-developer convention), ``IMG_0001.XMP``, then ``IMG_0001.CR3.xmp``."""
    photo = Path(photo)
    seen: set[str] = set()
    out: list[Path] = []
    for cand in (photo.with_suffix(".xmp"), photo.with_suffix(".XMP"), photo.with_name(photo.name + ".xmp")):
        key = os.path.normcase(str(cand))
        if key not in seen:
            seen.add(key)
            out.append(cand)
    return out


def find_sidecar(photo: Path) -> Path | None:
    for cand in sidecar_candidates(photo):
        if cand.is_file():
            return cand
    return None


def target_sidecar(photo: Path) -> Path:
    return find_sidecar(photo) or Path(photo).with_suffix(".xmp")


_XMP_HEADER = b"http://ns.adobe.com/xap/1.0/\x00"


def _jpeg_xmp(path: Path) -> bytes | None:
    with open(path, "rb") as fh:
        if fh.read(2) != b"\xff\xd8":
            return None
        for _ in range(64):
            marker = fh.read(2)
            if len(marker) < 2 or marker[0] != 0xFF:
                return None
            code = marker[1]
            if code == 0xDA or code == 0xD9:  # start of scan / end of image: metadata is over
                return None
            if code == 0x01 or 0xD0 <= code <= 0xD8:
                continue
            raw = fh.read(2)
            if len(raw) < 2:
                return None
            (length,) = struct.unpack(">H", raw)
            if length < 2:
                return None
            payload = fh.read(length - 2)
            if code == 0xE1 and payload.startswith(_XMP_HEADER):
                return payload[len(_XMP_HEADER):]
    return None


def extract_embedded(path: Path) -> bytes | None:
    """The XMP packet embedded in a JPEG, TIFF, PNG or WebP, if cheap to get (None otherwise)."""
    suffix = Path(path).suffix.lower()
    try:
        if suffix in (".jpg", ".jpeg"):
            data = _jpeg_xmp(Path(path))
        elif suffix in (".tif", ".tiff", ".png", ".webp"):
            from PIL import Image

            with Image.open(path) as img:
                if suffix in (".tif", ".tiff"):
                    value = img.tag_v2.get(700) if hasattr(img, "tag_v2") else None
                elif suffix == ".png":
                    value = img.info.get("XML:com.adobe.xmp")
                else:
                    value = img.info.get("xmp")
            data = value.encode("utf-8") if isinstance(value, str) else (bytes(value) if value else None)
            if data is not None and suffix in (".tif", ".tiff"):
                data = data.strip(b"\x00")
        else:
            return None
    except Exception:  # noqa: BLE001 - metadata is optional; a broken file never stops a scan
        return None
    if not data or len(data) > MAX_XMP_BYTES:
        return None
    return data

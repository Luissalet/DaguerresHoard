"""Retouch recipes as standard XMP sidecars: mapping, merge, safe reading, scan import, API and agent routes."""
from __future__ import annotations

import hashlib
import json
import os
import struct
import time

import pytest
from fastapi.testclient import TestClient

from daguerre_hoard import xmp
from daguerre_hoard.api import create_app
from daguerre_hoard.embeddings import FakeEmbedder
from tests.conftest import agent_headers, make_image

PORT = 18851

RECIPE = {
    "exposure": 0.5, "contrast": 12, "highlights": -30, "shadows": 25, "whites": 5, "blacks": -8,
    "vibrance": 15, "saturation": -4, "clarity": 10, "dehaze": 3,
    "temperature": 5600, "tint": -3,
    "crop": {"left": 0.1, "top": 0.05, "right": 0.95, "bottom": 0.9, "angle": 1.5},
    "orientation": 6,
}

# What a RAW developer typically leaves next to a RAW file: attributes on one rdf:Description, a keyword Seq,
# a hierarchical keyword Bag from another namespace, a tone curve, a title with a language Alt, no daguerre: data.
RAW_DEVELOPER_XMP = """<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 7.0-c000 1.000000, 0000/00/00-00:00:00">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:tiff="http://ns.adobe.com/tiff/1.0/"
    xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
    xmlns:lr="http://ns.adobe.com/lightroom/1.0/"
   xmp:Rating="3"
   xmp:Label="Red"
   tiff:Orientation="1"
   crs:Version="15.0"
   crs:ProcessVersion="11.0"
   crs:WhiteBalance="Custom"
   crs:Temperature="6100"
   crs:Tint="+8"
   crs:Exposure2012="+0.85"
   crs:Contrast2012="+14"
   crs:Highlights2012="-40"
   crs:Shadows2012="+22"
   crs:Whites2012="0"
   crs:Blacks2012="-10"
   crs:Vibrance="+18"
   crs:Saturation="0"
   crs:Clarity2012="+9"
   crs:Dehaze="+4"
   crs:Sharpness="40"
   crs:LuminanceSmoothing="12"
   crs:HasCrop="True"
   crs:CropTop="0.050000"
   crs:CropLeft="0.100000"
   crs:CropBottom="0.920000"
   crs:CropRight="0.960000"
   crs:CropAngle="-2.100000"
   crs:HasSettings="True">
   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">Harbour at dusk &amp; rain</rdf:li></rdf:Alt></dc:title>
   <dc:subject><rdf:Seq><rdf:li>harbour</rdf:li><rdf:li>dusk</rdf:li></rdf:Seq></dc:subject>
   <lr:hierarchicalSubject><rdf:Bag><rdf:li>places|harbour</rdf:li></rdf:Bag></lr:hierarchicalSubject>
   <crs:ToneCurvePV2012><rdf:Seq><rdf:li>0, 0</rdf:li><rdf:li>128, 140</rdf:li><rdf:li>255, 255</rdf:li></rdf:Seq></crs:ToneCurvePV2012>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""


# --------------------------------------------------------------------------- #
# xmp.py: recipe model and mapping
# --------------------------------------------------------------------------- #
def test_recipe_round_trip_through_xmp():
    recipe = xmp.validate_recipe_patch(RECIPE)
    data = xmp.merge_sidecar(None, xmp.SidecarEdits(recipe=recipe, rating=4, label="Blue", keywords=["trip", "sea"]))
    info = xmp.read_xmp(data)
    assert info.rating == 4 and info.label == "Blue" and info.keywords == ["trip", "sea"]
    assert info.daguerre_recipe == recipe  # the full recipe survives in daguerre:Recipe
    mapped, unmapped = xmp.crs_to_recipe(info.crs, exif_orientation=1, orientation=info.orientation)
    assert mapped == recipe and unmapped == {}  # and the standard crs: values alone rebuild it too
    text = data.decode("utf-8")
    assert 'crs:Exposure2012="+0.50"' in text and 'crs:HasCrop="True"' in text and 'tiff:Orientation="6"' in text
    assert text.startswith("<?xpacket begin=") and text.rstrip().endswith("<?xpacket end=\"w\"?>")


def test_recipe_validation_names_what_is_accepted():
    with pytest.raises(xmp.XmpError, match="Accepted: exposure, contrast"):
        xmp.validate_recipe_patch({"sepia": 3})
    with pytest.raises(xmp.XmpError, match="exposure must be between -5 and 5"):
        xmp.validate_recipe_patch({"exposure": 9})
    with pytest.raises(xmp.XmpError, match="right > left"):
        xmp.validate_recipe_patch({"crop": {"left": 0.8, "right": 0.2}})
    with pytest.raises(xmp.XmpError, match="EXIF orientation"):
        xmp.validate_recipe_patch({"orientation": 9})
    with pytest.raises(xmp.XmpError, match="must be a number"):
        xmp.validate_recipe_patch({"contrast": True})
    assert xmp.validate_recipe_patch({"contrast": "10", "dehaze": None}) == {"contrast": 10, "dehaze": None}


def test_reading_a_realistic_raw_developer_sidecar():
    info = xmp.read_xmp(RAW_DEVELOPER_XMP.encode("utf-8"))
    assert info.rating == 3 and info.label == "Red" and info.keywords == ["harbour", "dusk"]
    assert not info.written_by_daguerre and info.daguerre_recipe is None
    recipe, unmapped = xmp.crs_to_recipe(info.crs, exif_orientation=1, orientation=info.orientation)
    assert recipe["exposure"] == 0.85 and recipe["contrast"] == 14 and recipe["highlights"] == -40
    assert recipe["temperature"] == 6100 and recipe["tint"] == 8 and recipe["whites"] == 0
    assert recipe["crop"] == {"left": 0.1, "top": 0.05, "right": 0.96, "bottom": 0.92, "angle": -2.1}
    assert "orientation" not in recipe  # tiff:Orientation equal to the photo's own is not a retouch
    # what Daguerre cannot apply is kept as information, not dropped
    assert unmapped == {"Sharpness": "40", "LuminanceSmoothing": "12",
                        "ToneCurvePV2012": ["0, 0", "128, 140", "255, 255"]}


def test_out_of_range_values_are_not_applied_but_reported():
    recipe, unmapped = xmp.crs_to_recipe({"Exposure2012": "+7.5", "Contrast2012": "+10", "Temperature": "-20"})
    assert recipe == {"contrast": 10}
    assert unmapped == {"Exposure2012": "+7.5", "Temperature": "-20"}


def test_merge_keeps_every_foreign_field_and_updates_only_what_daguerre_owns():
    recipe = xmp.validate_recipe_patch({"exposure": -0.25, "contrast": 3})
    data = xmp.merge_sidecar(RAW_DEVELOPER_XMP.encode("utf-8"),
                             xmp.SidecarEdits(recipe=recipe, rating=5, keywords=["harbour", "rain"]))
    text = data.decode("utf-8")
    # kept: other namespaces and their prefixes, structured values, unmapped develop settings, title with language
    assert 'xmlns:lr="http://ns.adobe.com/lightroom/1.0/"' in text and "places|harbour" in text
    assert "ToneCurvePV2012" in text and "128, 140" in text
    assert 'crs:Sharpness="40"' in text and 'crs:LuminanceSmoothing="12"' in text
    assert 'xml:lang="x-default"' in text and "Harbour at dusk &amp; rain" in text
    assert 'xmp:Label="Red"' in text  # label was not part of this edit
    # updated: owned properties only
    assert 'xmp:Rating="5"' in text and 'crs:Exposure2012="-0.25"' in text and 'crs:Contrast2012="+3"' in text
    assert 'crs:Temperature="6100"' in text  # a crs setting the edit did not mention stays as the file had it
    assert "<rdf:li>rain</rdf:li>" in text and "<rdf:li>dusk</rdf:li>" not in text  # keywords were replaced as asked, in the existing Seq
    assert "<rdf:Seq>" in text.split("<dc:subject>")[1].split("</dc:subject>")[0]
    info = xmp.read_xmp(data)
    assert info.written_by_daguerre and info.keywords == ["harbour", "rain"] and info.rating == 5
    # merging again changes nothing but the timestamps
    again = xmp.merge_sidecar(data, xmp.SidecarEdits(recipe=recipe, rating=5, keywords=["harbour", "rain"], when="2026-01-01T00:00:00Z"))
    assert xmp.read_xmp(again).keywords == ["harbour", "rain"]
    assert again.decode("utf-8").count("<dc:subject>") == 1


def test_clearing_removes_only_what_was_cleared():
    recipe = xmp.validate_recipe_patch({"exposure": 1, "crop": {"left": 0.1, "right": 0.9}})
    data = xmp.merge_sidecar(None, xmp.SidecarEdits(recipe=recipe, rating=2, label="Green", keywords=["a"]))
    remaining, cleared = xmp.merge_recipe(recipe, {"crop": None})
    out = xmp.merge_sidecar(data, xmp.SidecarEdits(recipe=remaining, cleared=cleared, label="", keywords=[]))
    text = out.decode("utf-8")
    assert "CropLeft" not in text and "HasCrop" not in text and "xmp:Label" not in text and "dc:subject" not in text
    assert 'crs:Exposure2012="+1.00"' in text and 'xmp:Rating="2"' in text


@pytest.mark.parametrize("payload", [
    b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
    b'<!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">]><lolz>&lol2;</lolz>',
    b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY ext SYSTEM "file:///C:/Windows/win.ini">]><x>&ext;</x>',
    b'<?xml version="1.0"?><!DOCTYPE x SYSTEM "http://127.0.0.1:9/evil.dtd"><x/>',
    b'<!DOCTYPE x [<!ELEMENT x ANY>]><x/>',
])
def test_malicious_xml_is_rejected_before_anything_expands(payload):
    with pytest.raises(xmp.XmpError, match="DOCTYPE or entity"):
        xmp.read_xmp(payload)
    with pytest.raises(xmp.XmpError, match="DOCTYPE or entity"):
        xmp.merge_sidecar(payload, xmp.SidecarEdits(rating=1))


def test_oversized_deep_or_broken_documents_are_rejected():
    with pytest.raises(xmp.XmpError, match="larger than"):
        xmp.parse_xmp(b"<a>" + b"x" * (xmp.MAX_XMP_BYTES + 1) + b"</a>")
    with pytest.raises(xmp.XmpError, match="too large or too deeply"):
        xmp.parse_xmp(b"<a>" * 200 + b"</a>" * 200)
    with pytest.raises(xmp.XmpError, match="not valid XML"):
        xmp.parse_xmp(b"<a><b></a>")
    with pytest.raises(xmp.XmpError, match="no rdf:RDF"):
        xmp.read_xmp(b"<html><body/></html>")
    with pytest.raises(xmp.XmpError):
        xmp.merge_sidecar(b"not xml at all", xmp.SidecarEdits(rating=1))


def _jpeg_with_xmp(path, packet: bytes):
    make_image(path)
    raw = path.read_bytes()
    segment = b"http://ns.adobe.com/xap/1.0/\x00" + packet
    path.write_bytes(raw[:2] + b"\xff\xe1" + struct.pack(">H", len(segment) + 2) + segment + raw[2:])


def test_xmp_embedded_in_a_jpeg_is_extracted(tmp_path):
    p = tmp_path / "embedded.jpg"
    _jpeg_with_xmp(p, RAW_DEVELOPER_XMP.encode("utf-8"))
    assert xmp.read_xmp(xmp.extract_embedded(p)).rating == 3
    plain = make_image(tmp_path / "plain.jpg")
    assert xmp.extract_embedded(plain) is None


def test_sidecar_naming_follows_the_raw_developer_convention(tmp_path):
    assert xmp.target_sidecar(tmp_path / "IMG_0001.CR3") == tmp_path / "IMG_0001.xmp"
    (tmp_path / "IMG_0002.jpg.xmp").write_text("x", encoding="utf-8")
    assert xmp.find_sidecar(tmp_path / "IMG_0002.jpg") == tmp_path / "IMG_0002.jpg.xmp"


# --------------------------------------------------------------------------- #
# Library: storing, writing, scanning
# --------------------------------------------------------------------------- #
def _wait(library, job_id, timeout=15.0):
    start = time.time()
    while time.time() - start < timeout:
        job = library.jobs.get(job_id)
        if job and job["status"] in ("done", "error"):
            return job
        time.sleep(0.02)
    raise TimeoutError("scan did not finish")


def _scan(library, folder):
    root = library.add_root(str(folder))
    job = _wait(library, library.start_scan(root["id"]))
    assert job["status"] == "done", job
    return root, job


def _rescan(library, root):
    job = _wait(library, library.start_scan(root["id"]))
    assert job["status"] == "done", job
    return job


def _photo(library, name):
    return next(p for p in library.list_photos(limit=50)["results"] if p["path"].endswith(name))


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_sidecar_writing_is_off_by_default_and_edits_stay_in_daguerre(library, tmp_path):
    img = make_image(tmp_path / "photos" / "a.jpg")
    _scan(library, img.parent)
    pid = _photo(library, "a.jpg")["id"]
    assert library.xmp_sidecars_enabled() is False
    view = library.set_edits(pid, {"recipe": {"exposure": 0.4}, "rating": 4, "keywords": ["x"]})
    assert view["rating"] == 4 and view["recipe"] == {"exposure": 0.4} and view["keywords"] == ["x"]
    assert view["sidecar_write"]["written"] is False and "off" in view["sidecar_write"]["reason"]
    assert not (img.parent / "a.xmp").exists()
    from daguerre_hoard.library import ValidationError

    with pytest.raises(ValidationError, match="off"):
        library.write_sidecar(pid)


def test_write_creates_the_sidecar_next_to_the_photo_without_touching_the_photo(library, tmp_path):
    img = make_image(tmp_path / "photos" / "IMG_0001.jpg")
    before = (_sha(img), img.stat().st_mtime_ns)
    _scan(library, img.parent)
    library.set_xmp_sidecars(True)
    pid = _photo(library, "IMG_0001.jpg")["id"]
    view = library.set_edits(pid, {"recipe": RECIPE, "rating": 5, "label": "Red", "keywords": ["trip", "sea"]})
    side = img.parent / "IMG_0001.xmp"
    assert view["sidecar_write"]["written"] is True and view["sidecar_write"]["created"] is True
    assert side.is_file()
    assert (_sha(img), img.stat().st_mtime_ns) == before
    info = xmp.read_xmp(side.read_bytes())
    assert info.rating == 5 and info.label == "Red" and info.keywords == ["trip", "sea"]
    assert info.daguerre_recipe == xmp.validate_recipe_patch(RECIPE)
    # only the photo and its sidecar are in the folder: no temp files left behind
    assert sorted(p.name for p in img.parent.iterdir()) == ["IMG_0001.jpg", "IMG_0001.xmp"]
    # a second scan does not re-import Daguerre's own write
    root = library.list_roots()[0]
    assert _rescan(library, root)["stats"]["sidecars_read"] == 0
    assert view["sidecar"]["exists"] is True and library.get_edits(pid)["sidecar"]["changed_on_disk"] is False


def test_patch_semantics_merge_clear_and_validate(library, tmp_path):
    from daguerre_hoard.library import ValidationError

    img = make_image(tmp_path / "photos" / "a.jpg")
    _scan(library, img.parent)
    library.set_xmp_sidecars(True)
    pid = _photo(library, "a.jpg")["id"]
    library.set_edits(pid, {"recipe": {"exposure": 1.0, "contrast": 20}, "rating": 3, "label": "Blue", "keywords": ["a", "b"]})
    view = library.set_edits(pid, {"recipe": {"contrast": None, "shadows": 15}})
    assert view["recipe"] == {"exposure": 1.0, "shadows": 15} and view["rating"] == 3 and view["label"] == "Blue"
    text = (img.parent / "a.xmp").read_text(encoding="utf-8")
    assert "Contrast2012" not in text and 'crs:Shadows2012="+15"' in text
    view = library.set_edits(pid, {"rating": None, "label": "", "keywords": []})
    assert view["rating"] is None and view["label"] is None and view["keywords"] is None
    info = xmp.read_xmp((img.parent / "a.xmp").read_bytes())
    assert info.rating == 0 and info.label is None and info.keywords is None  # neutral values, not stale ones
    for bad, match in (({"recipe": {"exposure": 99}}, "between -5 and 5"), ({"rating": 9}, "-1 \\(rejected\\)"),
                       ({"keywords": "a,b"}, "list of words"), ({"colour": 1}, "Accepted: recipe, rating"),
                       ({}, "at least one"), ({"label": "x" * 80}, "at most 64")):
        with pytest.raises(ValidationError, match=match):
            library.set_edits(pid, bad)
    assert library.get_edits(pid)["recipe"] == {"exposure": 1.0, "shadows": 15}


def test_foreign_sidecar_is_backed_up_once_and_merged(library, tmp_path):
    img = make_image(tmp_path / "photos" / "IMG_7.jpg")
    side = img.parent / "IMG_7.xmp"
    side.write_text(RAW_DEVELOPER_XMP, encoding="utf-8")
    original = side.read_bytes()
    _scan(library, img.parent)
    library.set_xmp_sidecars(True)
    pid = _photo(library, "IMG_7.jpg")["id"]
    first = library.set_edits(pid, {"recipe": {"exposure": 0.1}, "keywords": ["harbour", "keeper"]})["sidecar_write"]
    assert first["written"] and first["merged"] and first["backup_of_original"]
    backup = tmp_path / "data" / "xmp-backups"
    assert [p.read_bytes() for p in backup.iterdir()] == [original]
    text = side.read_text(encoding="utf-8")
    assert "ToneCurvePV2012" in text and 'xmlns:lr=' in text and 'crs:Sharpness="40"' in text and "keeper" in text
    second = library.set_edits(pid, {"rating": 1})["sidecar_write"]
    assert second["written"] and "backup_of_original" not in second and len(list(backup.iterdir())) == 1


def test_unusable_existing_sidecar_is_never_overwritten(library, tmp_path):
    from daguerre_hoard.library import ValidationError

    img = make_image(tmp_path / "photos" / "a.jpg")
    side = img.parent / "a.xmp"
    side.write_text("<<< this is not xml", encoding="utf-8")
    _scan(library, img.parent)
    library.set_xmp_sidecars(True)
    pid = _photo(library, "a.jpg")["id"]
    result = library.set_edits(pid, {"rating": 2})
    assert result["rating"] == 2  # kept in Daguerre
    assert result["sidecar_write"]["written"] is False and "will not overwrite" in result["sidecar_write"]["error"]
    with pytest.raises(ValidationError, match="will not overwrite"):
        library.write_sidecar(pid)
    assert side.read_text(encoding="utf-8") == "<<< this is not xml"
    bomb = b'<!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]><x>&b;</x>'
    side.write_bytes(bomb)
    assert "will not overwrite" in library.set_edits(pid, {"rating": 3})["sidecar_write"]["error"]
    assert side.read_bytes() == bomb


def test_scan_imports_a_raw_developer_sidecar_as_a_starting_recipe(library, tmp_path):
    img = make_image(tmp_path / "photos" / "IMG_0042.jpg")
    (img.parent / "IMG_0042.xmp").write_text(RAW_DEVELOPER_XMP, encoding="utf-8")
    _, job = _scan(library, img.parent)
    assert job["stats"]["sidecars_read"] == 1
    pid = _photo(library, "IMG_0042.jpg")["id"]
    edits = library.get_edits(pid)
    assert edits["rating"] == 3 and edits["label"] == "Red" and edits["keywords"] == ["harbour", "dusk"]
    assert edits["recipe"]["exposure"] == 0.85 and edits["recipe"]["crop"]["angle"] == -2.1
    assert edits["source"] == "sidecar" and edits["sidecar"]["written_by"] == "foreign"
    assert edits["imported_not_applied"]["crs"]["Sharpness"] == "40"
    assert "ToneCurvePV2012" in edits["imported_not_applied"]["crs"]
    assert library.describe(pid)["edits"]["rating"] == 3  # photos_describe shows it too
    # the photo and the foreign sidecar are untouched by reading
    assert (img.parent / "IMG_0042.xmp").read_text(encoding="utf-8") == RAW_DEVELOPER_XMP


def test_scan_survives_a_malicious_sidecar_and_flags_it(library, tmp_path):
    img = make_image(tmp_path / "photos" / "bomb.jpg")
    bomb = (b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
            b'<!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">]><lolz>&lol1;</lolz>')
    (img.parent / "bomb.xmp").write_bytes(bomb)
    _, job = _scan(library, img.parent)
    assert job["stats"]["errors"] >= 1 and job["stats"]["sidecars_read"] == 0
    pid = _photo(library, "bomb.jpg")["id"]
    assert library.get_edits(pid)["sidecar"]["written_by"] == "invalid"
    assert (img.parent / "bomb.xmp").read_bytes() == bomb


def test_hand_edit_of_the_sidecar_is_read_on_rescan(library, tmp_path):
    img = make_image(tmp_path / "photos" / "a.jpg")
    _, _ = _scan(library, img.parent)
    root = library.list_roots()[0]
    library.set_xmp_sidecars(True)
    pid = _photo(library, "a.jpg")["id"]
    library.set_edits(pid, {"recipe": {"exposure": 0.5}, "rating": 2})
    side = img.parent / "a.xmp"
    text = side.read_text(encoding="utf-8").replace('xmp:Rating="2"', 'xmp:Rating="5"').replace("+0.50", "+1.25")
    side.write_text(text, encoding="utf-8")
    later = time.time() + 5
    os.utime(side, (later, later))
    job = _rescan(library, root)
    assert job["stats"]["sidecars_read"] == 1
    edits = library.get_edits(pid)
    assert edits["rating"] == 5 and edits["recipe"]["exposure"] == 1.25
    assert _rescan(library, root)["stats"]["sidecars_read"] == 0  # unchanged file: not read again


def test_an_edit_takes_a_sidecar_changed_on_disk_into_account_first(library, tmp_path):
    img = make_image(tmp_path / "photos" / "a.jpg")
    _scan(library, img.parent)
    library.set_xmp_sidecars(True)
    pid = _photo(library, "a.jpg")["id"]
    library.set_edits(pid, {"label": "Red", "rating": 1})
    side = img.parent / "a.xmp"
    side.write_text(side.read_text(encoding="utf-8").replace('xmp:Rating="1"', 'xmp:Rating="4"'), encoding="utf-8")
    later = time.time() + 5
    os.utime(side, (later, later))
    assert library.get_edits(pid)["sidecar"]["written_by"] == "daguerre"
    library.set_edits(pid, {"label": "Green"})
    info = xmp.read_xmp(side.read_bytes())
    assert info.rating == 4 and info.label == "Green"  # the hand edit to the rating was not overwritten


def test_embedded_xmp_gives_rating_and_keywords_but_never_a_recipe(library, tmp_path):
    _jpeg_with_xmp(tmp_path / "photos" / "export.jpg", RAW_DEVELOPER_XMP.encode("utf-8"))
    _, job = _scan(library, tmp_path / "photos")
    assert job["stats"]["embedded_read"] == 1
    pid = _photo(library, "export.jpg")["id"]
    edits = library.get_edits(pid)
    assert edits["rating"] == 3 and edits["keywords"] == ["harbour", "dusk"] and edits["source"] == "embedded"
    assert edits["recipe"] == {}  # the develop settings in a finished JPEG are already baked in
    assert "Exposure2012" in edits["imported_not_applied"]["crs"]
    assert edits["sidecar"]["exists"] is False


def test_losing_the_sidecar_keeps_the_edits(library, tmp_path):
    img = make_image(tmp_path / "photos" / "a.jpg")
    (img.parent / "a.xmp").write_text(RAW_DEVELOPER_XMP, encoding="utf-8")
    _, _ = _scan(library, img.parent)
    root = library.list_roots()[0]
    pid = _photo(library, "a.jpg")["id"]
    (img.parent / "a.xmp").unlink()
    _rescan(library, root)
    edits = library.get_edits(pid)
    assert edits["rating"] == 3 and edits["recipe"]["exposure"] == 0.85 and edits["sidecar"]["exists"] is False


def test_forgetting_a_folder_forgets_its_edits_and_leaves_sidecars(library, tmp_path):
    img = make_image(tmp_path / "photos" / "a.jpg")
    _, _ = _scan(library, img.parent)
    library.set_xmp_sidecars(True)
    pid = _photo(library, "a.jpg")["id"]
    library.set_edits(pid, {"rating": 2})
    library.remove_root(library.list_roots()[0]["id"])
    assert library.conn.execute("SELECT COUNT(*) FROM photo_edits").fetchone()[0] == 0
    assert (img.parent / "a.xmp").is_file()  # the owner's file is theirs


# --------------------------------------------------------------------------- #
# HTTP and agent routes
# --------------------------------------------------------------------------- #
@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("daguerre_hoard.library.select_embedder", lambda settings: FakeEmbedder())
    app = create_app(data_dir=tmp_path / "data", static_dir=None, port=PORT)
    with TestClient(app, base_url=f"http://127.0.0.1:{PORT}", headers=agent_headers(app)) as c:
        yield c


def _wait_http(client, job_id, timeout=15.0):
    start = time.time()
    while time.time() - start < timeout:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.02)
    raise TimeoutError("job did not finish")


def _http_photo(client, folder):
    root = client.post("/api/roots", json={"path": str(folder)}).json()
    _wait_http(client, client.post("/api/scan", json={"root_id": root["id"]}).json()["job_id"])
    return client.get("/api/photos").json()["results"][0]["id"], root


def test_http_and_agent_routes_for_edits(client, tmp_path):
    img = make_image(tmp_path / "photos" / "IMG_9.jpg")
    pid, root = _http_photo(client, img.parent)
    assert client.get("/api/settings").json()["xmp_sidecars"] is False

    # off: stored, reported, nothing on disk
    out = client.put(f"/api/photos/{pid}/edits", json={"rating": 4, "recipe": {"exposure": 0.7}}).json()
    assert out["rating"] == 4 and out["sidecar_write"]["written"] is False
    assert not (img.parent / "IMG_9.xmp").exists()
    refused = client.post("/api/agent/photos_sidecar", json={"photo_id": pid, "action": "write"})
    assert refused.status_code == 400 and "off" in refused.json()["message"]

    # on: the agent writes through the same Library call, audited
    assert client.post("/api/settings", json={"xmp_sidecars": True}).json()["xmp_sidecars"] is True
    done = client.post("/api/agent/photos_set_edits", json={
        "photo_id": pid, "recipe": {"contrast": 9}, "label": "Yellow", "keywords": ["x", "y"]}).json()
    assert done["sidecar_write"]["written"] and done["recipe"] == {"exposure": 0.7, "contrast": 9}
    side = img.parent / "IMG_9.xmp"
    assert side.is_file() and xmp.read_xmp(side.read_bytes()).rating == 4  # earlier edit is in the file too

    # hand edit + agent read
    side.write_text(side.read_text(encoding="utf-8").replace('xmp:Rating="4"', 'xmp:Rating="2"'), encoding="utf-8")
    later = time.time() + 5
    os.utime(side, (later, later))
    read = client.post("/api/agent/photos_sidecar", json={"photo_id": pid, "action": "read"}).json()
    assert read["read"] == "sidecar" and read["rating"] == 2
    got = client.post("/api/agent/photos_edits", json={"photo_id": pid}).json()
    assert got["rating"] == 2 and got["keywords"] == ["x", "y"] and "note" in got
    assert client.post(f"/api/photos/{pid}/sidecar/write").json()["sidecar_write"]["written"] is True
    assert client.post(f"/api/photos/{pid}/sidecar/read").json()["read"] == "sidecar"
    assert client.get(f"/api/photos/{pid}").json()["edits"]["label"] == "Yellow"

    calls = {c["tool"] for c in client.get("/api/agent-calls").json()}
    assert {"photos_sidecar", "photos_set_edits", "photos_edits"} <= calls
    # the UI's own clicks are not the assistant's activity
    assert client.get(f"/api/photos/{pid}/edits").status_code == 200

    # errors say what is accepted
    bad = client.post("/api/agent/photos_set_edits", json={"photo_id": pid, "recipe": {"sepia": 1}})
    assert bad.status_code == 400 and "Accepted: exposure" in bad.json()["message"]
    assert client.post("/api/agent/photos_set_edits", json={"photo_id": pid}).status_code == 400
    assert client.post("/api/agent/photos_edits", json={"photo_id": "f" * 32}).status_code == 404
    assert client.post("/api/agent/photos_edits", json={"photo_id": pid}, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_the_photo_is_byte_identical_after_every_xmp_operation(client, tmp_path):
    img = make_image(tmp_path / "photos" / "IMG_1.jpg")
    before = (_sha(img), img.stat().st_mtime_ns, img.stat().st_size)
    pid, _ = _http_photo(client, img.parent)
    client.post("/api/settings", json={"xmp_sidecars": True})
    client.put(f"/api/photos/{pid}/edits", json={"recipe": RECIPE, "rating": 5, "label": "Red", "keywords": ["k"]})
    client.post(f"/api/photos/{pid}/sidecar/read")
    client.post(f"/api/photos/{pid}/sidecar/write")
    assert (_sha(img), img.stat().st_mtime_ns, img.stat().st_size) == before


def test_ui_edit_form_sends_only_changed_fields_so_an_agent_edit_meanwhile_survives(client, tmp_path):
    """The edit form saves just the fields the user changed; the route must merge them and leave everything else."""
    img = make_image(tmp_path / "photos" / "IMG_7.jpg")
    pid, _root = _http_photo(client, img.parent)
    client.put(f"/api/photos/{pid}/edits", json={"rating": 2, "label": "Red", "keywords": ["a"], "recipe": {"exposure": 0.5}})
    # the assistant edits label and rating while the user's form (loaded earlier) is open
    client.post("/api/agent/photos_set_edits", json={"photo_id": pid, "label": "Green", "rating": 5})
    # the user saves only the keywords they typed
    out = client.put(f"/api/photos/{pid}/edits", json={"keywords": ["a", "b"]}).json()
    assert out["keywords"] == ["a", "b"]
    assert out["label"] == "Green" and out["rating"] == 5 and out["recipe"] == {"exposure": 0.5}
    # an explicit clear of one field is a change too and still leaves the rest
    out = client.put(f"/api/photos/{pid}/edits", json={"label": ""}).json()
    assert out["label"] is None and out["keywords"] == ["a", "b"] and out["rating"] == 5


def test_album_changes_merge_without_touching_the_rest(client, tmp_path):
    """Adding to an album by name keeps what it holds; removing some photos keeps the others (agent and UI can interleave)."""
    a = make_image(tmp_path / "photos" / "A1.jpg")
    make_image(tmp_path / "photos" / "A2.jpg", color=(10, 200, 10))
    pid, _root = _http_photo(client, a.parent)
    ids = [p["id"] for p in client.get("/api/photos").json()["results"]]
    assert len(ids) >= 2
    first = client.post("/api/albums", json={"name": "Trip", "photo_ids": [ids[0]]}).json()
    second = client.post("/api/albums", json={"name": "trip", "photo_ids": [ids[1]]}).json()
    assert second["id"] == first["id"] and second["photo_count"] == 2
    left = client.post(f"/api/albums/{first['id']}/remove", json={"photo_ids": [ids[0]]}).json()
    assert [p["id"] for p in left["photos"]] == [ids[1]]

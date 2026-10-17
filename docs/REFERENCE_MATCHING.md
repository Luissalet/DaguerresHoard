# Match exposure and colour to a reference

The photo lightbox can use an indexed photo as reference for the current photo
or up to 20 photos in the current view. Set strength, create copies and compare
the PNG outputs. Originals, XMP and existing retouch recipes remain unchanged.
The reference stays selected while navigating within the lightbox.

`photos_match_reference(reference_id, ids, strength=1, long_edge=1600)` is the
equivalent MCP tool. HTTP clients use `POST /api/photos/match-reference` or the
agent surface `/api/agent/photos_match_reference`. Both call `Library.match_photos`.
Output URLs and a JSON manifest live under the selected data directory; the
manifest records input fingerprints, measured before/after statistics, gains,
strength, dimensions and omissions. No foreign app or CLI is invoked.

The independent algorithm converts sRGB pixels to linear light, measures trimmed
geometric mean RGB among visible midtones, then applies per-channel gains to
align the target with the reference. Each channel is limited to three stops,
scaled by strength. Embedded ICC profiles are converted to sRGB; output is PNG
with alpha retained. Analysis uses at most 512 px; output long edge is 256–4096.

This is global exposure/colour matching for comparable scenes, not semantic
style transfer, local tone matching, RAW development or an image restoration
model. Differing scene content can produce unwanted colour shifts. Very dark,
clipped or transparent inputs without enough midtones are reported as omitted.
Inputs are originals; stored retouch recipes are not rendered. Use the existing
Layers/Develop editors for further work. Retrying creates another derivative;
returning to the original requires no undo because it was never edited.

Historical research reference: Rembrandt `0cea2d41ac0914d02f79f86e1e322fe8bff7cc6c`,
whose series-matching workflow motivated this capability. No source code,
application assets or model weights from that GPL-3.0 project are incorporated.

# Daguerre image engines

Daguerre incorporates the complete layered-image and development engines and desktop editors as detached Rust source. The owned binaries, model, formats and MCP resources evolve here. Original photos remain read-only; workflows import copies into configured Daguerre data.

## Build and use

See [owned engines](OWNED-ENGINES.md) for pinned provenance, licenses, builds and migration. Run `python scripts/build_engines.py` to build both engine/editor pairs; `--debug` selects the development profile. Runtime selects only `native/bin/daguerre-layers-cli` and `daguerre-develop-cli`. Historic external executable paths, PATH discovery and portable bundles no longer select an engine.

## Complete engine catalogues

`image_engines` reports owned executables. `image_tools(engine="layers"|"develop")` discovers the complete inner schemas and `image_call` executes a batch in the headless session or the running owned editor. Historic `photocraft`/`lightcraft` keys and `craft_*` tools remain aliases. The incorporated source retains the historical 18 layered-engine tools and 243 development tools; runtime discovery is the authority, and catalogue size is distinct from testing every operation.

## Photo workflows

`image_create_layered_document` creates a `.dglayers` project with editable background and overlay, plus PNG preview. `image_create_layered_photo(photo_id)` imports a copy of an indexed photo. `image_develop_photo(photo_id, exposure, output_format, long_edge)` imports a copy into the persistent owned development catalog and exports a derivative. Library indexing, metadata, search, albums and XMP recipes remain available.

The lightbox offers the same workflows, editable project download and an Open full editor button. `image_open_editor(artifact_id, engine)` opens the corresponding complete desktop editor on an owned copy. Native tools connect to that editor while it runs; when it closes, headless execution resumes. New layered files use `.dglayers`; historical `.pcraft` and development libraries remain importable without rewriting their originals. Flat exports are derivatives, not editable replacements for originals.

Preferred local routes use `/api/image-engine/status`, `/from-photo`, `/develop`, `/import-compositor`, and `/editor`. Preferred agent routes are `/api/agent/image_*`. All original routes remain available. Both HTTP and MCP call the same library implementation; generated outputs and editor preferences stay under configured Daguerre data.

### Import a Compositor package

`craft_import_compositor(source_path, preflight_only=false)` is available through
MCP, audited `POST /api/agent/craft_import_compositor`, and local
`POST /api/craft/import-compositor`. Select an existing `.comp` directory;
compressed archives are unsupported. `preflight_only=true` reads and validates
without starting Daguerre Layers or writing an intake. Read `status` before using
the result: `ready` is a successful preflight, `blocked` rejects unsupported
content, `imported` includes artifacts, and `failed` includes a runtime error
receipt. A blocked package creates no native project and never falls back to
flattened pixels.

The supported subset is Compositor schema 1–11, sRGB, 1–128 ungrouped pixel
layers, single-frame unprofiled 8-bit RGB/RGBA PNG assets, Normal blending,
names, visibility, opacity, native image dimensions and integer offsets.
Canvas/image sides are 1–8192 pixels; source pixels total at most 100 million,
encoded image bytes total at most 512 MiB, and manifest size at most 4 MiB.
Resolution is 1–9600 ppi. Empty pixel layers are retained. Unsupported groups,
masks, adjustments, text, shapes, effects, guides, blends, resampling, rotation,
flips, fractional offsets, embedded ICC profiles and unknown fields block the
whole import with per-layer/property reasons. Future schemas are rejected.

Daguerre snapshots the exact manifest and referenced PNG bytes into its private
workspace, retaining SHA-256 hashes and source UUID provenance. The original
package is read only. Ancillary package files such as QuickLook are not copied.
Daguerre Layers receives scoped `doc_open` paths, then native copy/paste-in-place,
property and integer translation commands in one headless session. Separate
layers stay editable. Native IDs replace UUIDs; the receipt records the mapping.
Source active selection is omitted because Daguerre Layers reopens with its default
selection. Undo and viewport state are not imported.
Fully transparent PNG assets are rejected (blank layers without an asset are
supported). Native copy/paste trims fully transparent margins; the preflight
explicitly reports this representation change, retains the complete original
PNG, and verifies the visible content's resulting bounds. Blank-layer source
rectangles are retained only in provenance and reported as transformed.

The importer saves `.dglayers`, reopens it, checks layer order/names/visibility/
opacity/type and dimensions, and compares SHA-256 of PNG exports before and
after reopen. It returns native/preview/download paths, engine executable hash,
source hashes, native readback and all actual MCP calls. The JSON receipt is
served under `/api/craft/artifacts/<id>.json`; `.dglayers` and PNG use the same ID.
A runtime failure deletes unpublished native/preview outputs and retains the
input snapshot and failure receipt for diagnosis.

This is a verified native workflow, **not Compositor renderer or format parity**.
Compositor cannot run on this Windows machine; appearance against its renderer
remains unverified. Its documented format is pinned at
[`11d8d7a`](https://github.com/robbietilton/Compositor/blob/11d8d7a50992b24fd9a760a1c13b1c01b70aaf30/docs/project-format.md).
The implementation follows the public specification and copies no upstream code.
Real native tests cover two three-layer packages, opacity 0.5, positive/negative
offsets, hidden RGBA content, 144 ppi, identical save/reopen PNG hashes, and
revealing an imported hidden layer through native commands. Use
`pytest tests/test_compositor.py -m craft_integration` with configured bundles;
optional `DAGUERRE_COMPOSITOR_EVIDENCE` retains synthetic evidence under a selected
test directory. Negative cases cover missing/damaged/unsafe assets, unknown
fields, future versions and unsupported editable content before native launch.

| Reference capability | Import status | Evidence / gap |
| --- | --- | --- |
| Raster PNG, layer order/name/visibility/opacity | Implemented subset | Native `.dglayers` reopen, synthetic 3-layer fixtures, source SHA-256 |
| Integer raster placement and document resolution | Implemented | Positive/negative native bounds, 144 ppi; source-over pixel checks |
| RGBA margins and empty layers | Transformed explicitly | Native visible bounds verified; full source frame retained in snapshot |
| Other blends, scale/rotate/flip, fractional placement | Blocked | Negative preflight; renderer equivalence unverified |
| Groups / inherited visibility / pass-through opacity | Blocked | No flattening; negative group and parent cases |
| Raster/group/unlinked/live clipping masks | Blocked | No editable mapping verified |
| All adjustment kinds / editable text / color and font runs | Blocked | Negative adjustment/text tests; semantic equivalence unverified |
| Shape geometry / effects / guides | Blocked | Negative shape/effect cases; mapping unverified |
| Active selection / undo / viewport | Omitted | Receipt states omissions; native selection defaults on reopen |
| Full `.comp` load and reverse export | Incomplete | Only directory subset; schema 1–11 and unknown-field rejection; no reverse export |
| Compositor UI and complete photo editor workflows | Unimplemented | Existing Daguerre API/MCP workflow; no new import screen or UI parity claim |
| Automation / errors / retries | Implemented subset | Audited API, stdio MCP import, bounded read-only preflight, native failure receipt; each retry produces a new ID |

The added capability makes this verified subset available to local API/MCP
clients with explicit provenance and rejection receipts. It is an incremental
interchange improvement, not an established replacement or superiority claim.
[Guía en español](COMPOSITOR.es.md).

## Scope and verification

Both complete engines and desktop UIs are incorporated, including their existing codec, development, layered document and automation implementations. Specific runtime tests are documented separately; no claim certifies every RAW variant, command or export combination. The Compositor raster subset and unsupported-property reporting above are retained.

After building, enable `DAGUERRE_NATIVE_TESTS=1` and run `pytest -m craft_integration` for actual incorporated engines with private synthetic data. The normal suite excludes the real CLIP model. Do not place synthetic test data in a personal photo library.

## Licenses and provenance

`native/layers` and `native/develop` retain original MIT/Apache licenses, NOTICE and historical ASSETS attribution. Fonts and the spelling dictionary retain their own license texts. Application icons come from the existing Hoard. PROVENANCE.json fixes original revisions and per-file source hashes; no origin repository or executable is a runtime dependency.

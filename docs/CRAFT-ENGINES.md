# Local Craft engines

Daguerre can launch the portable PhotoCraft and LightCraft command-line
engines locally. The engines keep their native formats and their own MCP
tools. Daguerre supplies photo-library context, local discovery, audit logs,
and safe output locations; it does not claim full feature parity with either
editor.

## Install and configure

Keep the upstream release bundles outside the repository. Daguerre discovers
`photocraft-cli.exe` and `lightcraft-cli.exe` in either `data/craft-apps/` or
`data/craft-bundles/`, including one portable release directory below those
folders. A shared portable bundle folder can be selected with
`DAGUERRE_CRAFT_BUNDLES`. For explicit paths, create `data/craft-engines.json`:

```json
{
  "photocraft": "D:/Apps/photocraft-cli.exe",
  "lightcraft": "D:/Apps/lightcraft-cli.exe"
}
```

The JSON paths take precedence over `DAGUERRE_PHOTOCRAFT_CLI` and
`DAGUERRE_LIGHTCRAFT_CLI`; those environment variables take precedence over
automatic discovery and `PATH`. `/api/craft/status` and the `craft_engines`
MCP tool show availability and the resolved paths. App data, isolated
workspaces, LightCraft's library, and generated files stay below Daguerre's
configured `data/` directory.

## Full upstream MCP surface

Use `craft_tools(engine)` to start the selected headless engine briefly and
read its live MCP tool names, descriptions, and JSON schemas. On the inspected
Windows x64 releases, PhotoCraft v0.2.0 advertised 18 MCP tools and LightCraft
v0.2.1 advertised 243. These are release-specific catalog sizes, not counts
for every release. Use `craft_call(engine, calls)` to send 1–32 native MCP
calls in one session. Each call is `{ "tool": "upstream_name", "arguments":
{...} }`; a sequence shares its live editor session, and every actual
upstream result and failure is returned. The app's own catalog remains live
and schemas are not reimplemented or frozen in Daguerre.

PhotoCraft's child is launched with its own explicit read and write roots at
`data/craft-workspace/`, so its file tools cannot reach a registered photo
root. LightCraft has no equivalent documented root switch; Daguerre therefore
rejects absolute file paths outside its workspace and generated output folder,
and rejects `..` path traversal. Put files to process in the workspace first.
The high-level photo workflow makes a copy there automatically.

## Integrated workflows

### Develop an indexed photo

Call `craft_develop_photo(photo_id, exposure, output_format="png",
long_edge=0)`. `photo_id` comes from Daguerre search; exposure is -5 to +5 EV.
Daguerre copies the original bytes to its private workspace, imports that copy
into LightCraft's persistent local library, applies `light.exposure`, and
exports a derivative under `data/craft-outputs/`. The result includes the
LightCraft calls, local path, preview URL, and `original_modified: false`.
Source photos remain read-only.
The photo lightbox also exposes this operation with an exposure slider and
shows the exported derivative when it completes.

### Open an editable photo copy

`craft_create_layered_photo(photo_id)` copies the selected indexed image into
the PhotoCraft read root, opens it with the scoped `doc_open` MCP tool, adds an
editable pixel overlay, saves a `.pcraft` project, and exports a PNG preview.
The lightbox offers the same action and links the native project for download.
The workflow uses PhotoCraft's document-scoped relative path interface; it
does not call ambient-path commands. The source file is never given to
PhotoCraft directly.

### Create an editable layered raster document

Call `craft_create_layered_document(name, width=512, height=384,
background="#315c7e")`. It creates a native `.pcraft` document with an editable
background and pixel overlay, then exports a PNG preview. Both files remain in
`data/craft-workspace/exports/`; the preview is served under
`/api/craft/artifacts/<random-id>.png`.

The normal local UI endpoints are `POST /api/craft/from-photo` and
`POST /api/craft/develop`; both are also available through authenticated,
audited `/api/agent/*` endpoints and the corresponding MCP tools. The separate
Compositor `.comp` package import has a strict raster subset, described below.

### Import a Compositor package

`craft_import_compositor(source_path, preflight_only=false)` is available through
MCP, audited `POST /api/agent/craft_import_compositor`, and local
`POST /api/craft/import-compositor`. Select an existing `.comp` directory;
compressed archives are unsupported. `preflight_only=true` reads and validates
without starting PhotoCraft or writing an intake. Read `status` before using
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
PhotoCraft receives scoped `doc_open` paths, then native copy/paste-in-place,
property and integer translation commands in one headless session. Separate
layers stay editable. Native IDs replace UUIDs; the receipt records the mapping.
Source active selection is omitted because PhotoCraft reopens with its default
selection. Undo and viewport state are not imported.
Fully transparent PNG assets are rejected (blank layers without an asset are
supported). Native copy/paste trims fully transparent margins; the preflight
explicitly reports this representation change, retains the complete original
PNG, and verifies the visible content's resulting bounds. Blank-layer source
rectangles are retained only in provenance and reported as transformed.

The importer saves `.pcraft`, reopens it, checks layer order/names/visibility/
opacity/type and dimensions, and compares SHA-256 of PNG exports before and
after reopen. It returns native/preview/download paths, engine executable hash,
source hashes, native readback and all actual MCP calls. The JSON receipt is
served under `/api/craft/artifacts/<id>.json`; `.pcraft` and PNG use the same ID.
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
| Raster PNG, layer order/name/visibility/opacity | Implemented subset | Native `.pcraft` reopen, synthetic 3-layer fixtures, source SHA-256 |
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

The integrated workflows exercise real native MCP calls and preserve the
PhotoCraft document or LightCraft develop library. The LightCraft PNG/JPEG/etc.
is a rendered derivative; it is not an editable substitute for the RAW/photo
source. Daguerre does not yet offer PhotoCraft's complete UI, PSD/PSB import
and export matrix, batch/droplet workflows, every LightCraft catalog/develop
operation, masks, merge, preset management, or UI automation as first-class
Daguerre screens. They remain accessible through the upstream live tool
catalogue subject to the isolated file boundary. Feature parity and superiority
have not been established.

The opt-in `craft_integration` tests launch configured local executables with
disposable data and synthetic images. Set `DAGUERRE_CRAFT_BUNDLES` to the
directory holding the portable release folders, then run
`pytest -m craft_integration`. They verify editable layer presence, real export,
exposure effect, and original-byte preservation. Do not point tests or imports
at a personal photo library.

## Licenses

The inspected PhotoCraft and LightCraft release bundles include MIT and Apache
license files for their code. Review bundled fonts, models, presets, sample
media, and other assets separately before redistribution; this integration
does not copy Craft binaries or bundled assets into Daguerre.

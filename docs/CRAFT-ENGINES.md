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
Compositor `.comp` package format is not imported or exported yet: its layer
transforms, masks, adjustment layers and other properties are not mapped to
PhotoCraft's native project model here.

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

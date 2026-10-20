# Retained diagram figures

The common Projects workbench accepts complete `vitruvius.figure/1` JSON files
(`.vfigure`). The source document, its revision, optional page or isometric state,
origin links, future optional fields and the exact PNG capture stay together.
Importing, inspecting, reopening and downloading a capture work with both native
modules OFF. Origin links open only when selected; importing fetches no remote data.

In a selected project choose **Import figure (.vfigure)**. **Inspect figure** opens
the retained image with Actual size, 2×, Fit, keyboard scrolling and Escape. Closing
returns focus to the opener. Importing or inspecting does not submit the separate
new-project title field. Invalid files leave existing captures intact.

Activate the destination explicitly before choosing **Create in Vector** or
**Create in Layers**. Vector creates a native illustration containing the PNG;
Layers creates a `.dglayers` document with the PNG and an editable overlay layer.
These are raster copies: they do not recreate semantic diagram nodes, connectors,
mechanism states or source text as native editing objects. Keep the `.vfigure`
source to continue diagram authoring in its originating editor. A later import is
a new immutable capture unless its complete content is identical; there is no
automatic synchronization. Equal PNGs with different source, revision, page or
state remain distinct captures.

Native copies use owned files under the profile, never registered photo originals.
Layers accepts 16–8192 pixels per dimension; other valid PNG sizes can still be
retained and downloaded. A failed or timed-out native creation does not record a
completed transfer or discard the capture. Its error identifies the native copy
to inspect before retrying; a partial native document can remain available for
recovery. Module shutdown waits for an already dispatched write.

## Shared HTTP and MCP operation

The host adds `visual_project_figure`, bringing the cold catalogue to **96 tools**:
31 Photos, 57 Vector aliases and 8 common operations. No engine starts on discovery.
Actions `import`, `get`, `vector` and `layers` use the same implementation as
`POST /api/studio/projects/{project}/figure`. `project` is required; native actions
and `get` take `object_id`, while `import` takes the complete `figure` object.

```json
{"project":"<project-id>","action":"import","figure":{"format":"vitruvius.figure/1","document_id":"<12-hex-id>","revision":1,"content":{"diagram":{"nodes":[]}},"preview":{"mime":"image/png","data":"<base64>"}}}
```

Import/get return `id`, `project`, `revision` (the complete-capture fingerprint),
`png_url` and `source_url`; get also returns `figure` in full. Download routes
`GET /api/studio/figures/{project}/{object}.png` and `.vfigure` use the retained
database snapshot and remain available while native modules are OFF. The source
revision number remains in `figure.revision`, separately from the fingerprint.
Native actions return the project with the new object and transfer receipt.

Complete JSON and actual PNG decoding are validated before a capture is published.
The object insert and owned file publication roll back together on ordinary write
failure. The source JSON is preserved semantically, including unknown fields;
download formatting and key order need not match the imported file bytes.

## Verification boundary

Task1061 checks cover complete source/history, concurrent deduplication, invalid
imports, failed file publication, partial native failure recovery, cancelled
waiters and Layers dimensions. Real owned CPU checks use native Vector and Layers
through MCP, export pixel-identical PNGs, retain full source and reopen Vector.
Browser checks cover desktop/mobile, both themes, imports/downloads while OFF,
keyboard inspection, preserved drafts and both native creation buttons. No model
is loaded and no real library is opened. Desktop GUI save dialogues, semantic
vector reconstruction and automatic origin synchronization are outside this flow.

# Export a selection from the photo library

In Photos, use **Export selection** in the library or search results, then select
photos in the desired order. **Select first 20 loaded** selects the first visible
page items; it never means the whole library. Name the gallery and export.
In an album, use its existing **Select photos** control and select the photos to
export. Removing a photo from an album remains a separate operation.

The result provides:

- A self-contained HTML gallery with embedded JPEG previews, which opens without
  Daguerre or an internet connection.
- A numbered JPEG contact sheet and a preview in the interface.
- A JSON manifest with source identifiers, fingerprints, dimensions and omissions.

These are previews up to 512 px, not full-resolution original downloads. The
existing native export contract accepts 1–20 photos. Selection order is retained;
the UI shows the names in that order before exporting. Unavailable or unreadable
sources are reported by the native exporter; a partial result says how many were
included and points to the manifest for details. Originals, albums and retouch
recipes are unchanged.

The UI calls `POST /photos/api/photos/export` in the visual studio (or
`POST /api/photos/export` in the standalone photo API). It shares
`Library.export_photos` with the existing `photos_export` MCP tool; the native
gallery, contact-sheet and manifest file endpoints are reused. User clicks are
not recorded as assistant tool calls. Export files remain in the selected
Daguerre data directory.

References studied: [PhotoPrism selection and multi-select](https://docs.photoprism.app/user-guide/navigate/)
and [darktable export selected images](https://docs.darktable.org/usermanual/development/en/module-reference/utility-modules/shared/export/).
They inform discoverable selection actions; no source code or runtime dependency
from either project is incorporated, and no feature parity is claimed.

# MCP tools

Argus's Hoard exposes 9 tools over stdio (`argus_hoard/mcp_server.py`).
Every tool calls the app's own `/api/agent/<tool>` HTTP endpoint, so the
behaviour is identical whether a model reaches it through MCP or an
HTTP-only client calls the API directly, and both are covered by the same
tests (`tests/test_api.py` for the HTTP layer, `tests/test_mcp_protocol.py`
for the real MCP protocol round trip).

All tools are read-only except `photos_add_folder` (adds a root, never
removes one) and `photos_album` (creates/extends an album, never deletes
one). `photos_describe(caption=true)` is the only tool that writes
anything to a photo's record, and it only writes a generated caption.

Connect any stdio MCP client with:

```json
{
  "mcpServers": {
    "argus": {
      "command": "/absolute/path/to/argus-hoard/.venv/Scripts/python.exe",
      "args": ["/absolute/path/to/argus-hoard/argus_hoard/mcp_server.py"],
      "env": { "ARGUS_URL": "http://127.0.0.1:8814" }
    }
  }
}
```

`ARGUS_URL` must be a loopback address (`127.0.0.1` or `localhost`); the
adapter refuses anything else at startup.

## photos_search

Search photos by what is in them. **Translate `query` to English first** --
the CLIP model matches English text noticeably better.

| param | type | default | notes |
| --- | --- | --- | --- |
| `query` | string | required | free text, English |
| `taken_after` / `taken_before` | ISO date string | none | inclusive |
| `year` | int | none | |
| `month` | int (1-12) | none | |
| `place` | string | none | substring match on city/country |
| `folder` | string | none | substring match on the file path |
| `camera` | string | none | substring match on make/model |
| `orientation` | `"landscape"` \| `"portrait"` | none | |
| `min_megapixels` | float | none | |
| `has_gps` | bool | none | |
| `limit` | int | 12 | max photos returned |
| `contact_sheet` | bool | true | attach a numbered contact-sheet image |

Returns `{query, count, results: [{id, path, taken_at, place, size, width,
height, thumbnail_url, score}], truncated}` plus, over MCP, one
`ImageContent` JPEG (<=200 KB) with a numbered badge per result.

## photos_similar

`photo_id` (preferred) or `path`, `limit` (default 12), `contact_sheet`
(default true). Same result shape as `photos_search` minus `query`.

## photos_show

`ids` (list, first 4 used), `size` (default 768, longest side in pixels).
Returns one `ImageContent` JPEG per id, plus `{"ids": [...]}` metadata.
Use this when the contact sheet is not enough detail.

## photos_describe

`photo_id` (required), `caption` (default false). Returns the full record:
EXIF (make, model, lens, f_number, exposure_time, iso, focal_length,
orientation), `gps_lat`/`gps_lon`, `city`/`region`/`country`, `path`,
`content_hash`, `indexed_at`, and `caption` if one exists or was just
generated. If `caption=true` and Ollama is unreachable, the result carries
`caption_error` instead of failing the whole call.

## photos_duplicates

`kind` (`"exact"` default, or `"near"`), `limit` (default 10). Returns
`{kind, count, groups: [{kind, keeper_id, max_distance, photos: [...]}]}`.
`keeper_id` is chosen by largest resolution, then oldest `taken_at`, then
shortest path. Argus never deletes anything -- this is information for a
human to act on.

## photos_timeline

`year` (optional int). Returns `{years: {"2024": {"01": 5, ...}, ...},
on_this_day: [{id, taken_at, place}], year?: {...}}`.

## photos_library

No parameters. Returns `{roots: [...], photo_count, missing_count,
embedder: {name, dim}, geocoder_source, recent_jobs, ollama: {base_url,
model}}`. Call this first if unsure whether anything is indexed.

## photos_add_folder

`path` (absolute). Registers a new root and starts a background indexing
job. Returns `{root: {...}, job_id}`. **Adds only** -- there is no
`photos_remove_folder` tool; removing a root is a human action in the
Settings screen.

## photos_album

`name`, `photo_ids` (list). Creates the album if it does not exist,
otherwise adds photos to it. Returns `{id, name, created_at, photos: [...],
added}`.

## Errors

Every tool raises `ToolError` with a plain-text message on failure. A
photo/album not found: `"not_found: <message>"`-shaped detail from the
API. The app not running: `"argus_unavailable: Argus's Hoard is not
running. Start it from Faustus (Apps) or with 'Iniciar Argus.cmd', then
retry."`

## Limits

Results default to 10-12 items; contact sheets are capped at ~200 KB;
`photos_show` returns at most 4 images. Every photo has a stable `id`
(a UUID) that survives file moves/renames, safe to pass back into any
other tool.

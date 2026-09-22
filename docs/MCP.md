# MCP tools

Argus's Hoard exposes 9 tools over stdio (`argus_hoard/mcp_server.py`, a
standalone script: stdlib + `httpx` + `mcp`). Every tool calls the app's
own `/api/agent/<tool>` endpoint and returns exactly what that endpoint
returns, so an HTTP-only client gets the same data. The HTTP layer is
covered by `tests/test_api.py` and `tests/test_security.py`; the real MCP
protocol round trip (the adapter spawned over stdio against a live app) by
`tests/test_mcp_protocol.py`.

Every call made through these endpoints is written to the `agent_calls`
table and shown in the app under **Assistant activity** (tool, arguments,
duration, result or error). The app's own interface uses separate routes,
so the owner's clicks never appear there.

## Connecting

```json
{
  "mcpServers": {
    "argus": {
      "command": "C:/path/to/argus-hoard/.venv/Scripts/python.exe",
      "args": ["C:/path/to/argus-hoard/argus_hoard/mcp_server.py"],
      "env": { "ARGUS_URL": "http://127.0.0.1:8814" }
    }
  }
}
```

`ARGUS_URL` must be an `http://` loopback address (`127.0.0.1` or
`localhost`); the adapter exits at start-up otherwise, and it ignores
system proxy settings for these calls.

## Conventions

- Text results are **compact JSON** (no indentation, UTF-8), about a third
  fewer tokens than pretty-printed JSON.
- Every photo has a stable `id` (32 hex characters) that survives renames
  and moves (same bytes at a new path keep their id). Pass it back to any
  other tool.
- Search results carry `n` (1, 2, 3...), the number printed on the
  matching cell of the contact sheet.
- `score` is the cosine similarity between the query and the photo
  (roughly 0.2-0.35 for a good CLIP match; only the ranking matters).
- When the image model is not downloaded, results carry `"embedder":
  "fake-colorhist-v1"` and a `note` saying search only understands colour
  words. The model should pass that on instead of trusting the ranking.
- Lists are short by default and say when there is more (`has_more`,
  `total_groups`, `on_this_day_count`).

| tool | read-only | idempotent | purpose |
| --- | --- | --- | --- |
| `photos_search` | yes | yes | text (English) -> photos + contact sheet |
| `photos_similar` | yes | yes | photos that look like a given photo |
| `photos_show` | yes | yes | up to 4 images for close inspection |
| `photos_describe` | yes* | yes | EXIF, place, path; optional local caption |
| `photos_duplicates` | yes | yes | exact / near duplicate groups + keeper |
| `photos_timeline` | yes | yes | counts per year/month, on this day |
| `photos_library` | yes | yes | folders, counts, model, running jobs |
| `photos_add_folder` | no (adds) | yes | register a folder and index it |
| `photos_album` | no (adds) | yes | create or extend an album |

\* `photos_describe(caption=true)` stores the generated caption in Argus's
own database (the photo file is never touched). All annotations set
`destructiveHint=false` and `openWorldHint=false`.

## photos_search

| param | type | default | notes |
| --- | --- | --- | --- |
| `query` | string | required | describe the photo **in English** |
| `taken_after` / `taken_before` | ISO date or datetime | none | inclusive; a plain date covers the whole day |
| `year` | int | none | 1800-2200 |
| `month` | int | none | 1-12 |
| `place` | string | none | substring of city, region or country |
| `folder` | string | none | substring of the path, either slash direction |
| `camera` | string | none | substring of make or model |
| `orientation` | `"landscape"` or `"portrait"` | none | |
| `min_megapixels` | float | none | |
| `has_gps` | bool | none | `false` finds photos without GPS |
| `limit` | int | 12 | 1-50 |
| `contact_sheet` | bool | true | attach the numbered contact sheet |

Returns
`{query, count, has_more, embedder, results: [{n, id, path, taken_at, place, size, width, height, thumbnail_url, score, caption_match?}]}`
and one JPEG `ImageContent` (5 columns, at most 20 cells, at most 200 KB).
When captions exist, ranking is hybrid: 0.8 x normalised cosine + 0.2 x
normalised BM25 over the captions (`caption_match: true` marks those hits).

Bad input is an error the model can fix, e.g.
`invalid_argument: unknown filter(s): city. Valid filters: taken_after, ...`
or `invalid_argument: month must be 1-12, got 13`.

## photos_similar

`photo_id` (preferred) or `path` (absolute), `limit` (1-50, default 12),
`contact_sheet` (default true). Returns `{photo_id, count, has_more,
embedder, results: [...]}` with the photo itself excluded, plus a contact
sheet.

## photos_show

`ids` (list; first 4 distinct ids used), `size` (128-1024, default 768,
long side in pixels). Returns `{shown: [{id, path, taken_at}], not_found:
[...], unreadable?: [...], ignored_ids?: [...]}` followed by one JPEG per
shown photo, each at most 200 KB (quality, then size, is lowered to fit).
EXIF rotation is applied.

## photos_describe

`photo_id` (required), `caption` (default false). Returns `{id, path,
taken_at, date_source, place, size, width, height, thumbnail_url, make,
model, lens, f_number, exposure_time, iso, focal_length, orientation,
gps_lat, gps_lon, city, region, country, caption}`; fields without data
are omitted. `date_source` is `exif` or `file_mtime` (no EXIF date). With
`caption=true` and no caption yet, the photo (downscaled to 1024 px) is
sent to the configured local Ollama vision model; if that fails the
result carries `caption_error` instead of failing the call.

## photos_duplicates

`kind` (`"exact"` default, or `"near"`), `limit` (1-50 groups, default
10). Returns `{kind, count, total_groups, has_more,
reclaimable_bytes_total, groups: [{kind, keeper_id, max_distance,
reclaimable_bytes, photos: [...]}]}`, groups with the most wasted space
first and the keeper listed first. Exact = identical BLAKE2b content hash;
near = perceptual hash (pHash) within Hamming distance 6, grouped with
union-find (pure exact-copy groups are left to `kind="exact"`). Keeper:
largest resolution, then oldest `taken_at`, then shortest path. Argus
never deletes anything.

## photos_timeline

`year` (optional). Without it: `{years: {"2024": 812}, months: {"2024":
{"03": 40}}, on_this_day: [{id, taken_at, place, thumbnail_url}],
on_this_day_count}`. With it: `{year, total, months: {"2024": {...}},
on_this_day, on_this_day_count}`. `on_this_day` lists at most 10 photos
taken on today's month and day in earlier years.

## photos_library

No parameters. Returns `{roots: [{id, path, photo_count, exists}],
photo_count, missing_count, indexing, embedder: {name, dim, semantic,
stale_photos}, geocoder_source, heic_support, recent_jobs: [{id, kind,
status, progress, message}], note?}`. `semantic: false` means content
search needs the model download; `stale_photos` are photos still to be
embedded with the active model.

## photos_add_folder

`path` (absolute, existing folder, not inside Argus's data folder).
Registers the root (or finds the existing one) and starts an index job.
Returns `{root: {id, path, photo_count}, job_id, next}`. There is no tool
to remove a folder: that is a human action in Settings.

## photos_album

`name` (1-100 characters, matched case-insensitively), `photo_ids` (up to
500). Creates the album or adds to it; nothing is ever removed. Returns
`{id, name, created_by, created, added, unknown_ids, photo_count,
has_more, photos: [first 10]}`.

## Errors

Tool failures raise `ToolError` with `<code>: <message>`, taken from the
app's `{error, message}` response:

| code | when |
| --- | --- |
| `invalid_argument` | a parameter is missing or out of range; the message lists what is accepted |
| `not_found` | unknown photo id / path / album; the message says where valid ids come from |
| `internal_error` | an unexpected failure (also recorded in Assistant activity) |
| `argus_unavailable` | the app is not running: "Start it from Faustus (Apps) or with 'Iniciar Argus.cmd', then retry." |
| `argus_timeout` | no answer within 120 s (a big scan may be running); retry once |

## Limits

Default result sizes are 10-12 items, at most 50; contact sheets show at
most 20 photos and weigh at most 200 KB; `photos_show` returns at most 4
images of at most 200 KB each. Vector search is brute-force cosine over a
memory-mapped float32 matrix, fine to about 200k photos.

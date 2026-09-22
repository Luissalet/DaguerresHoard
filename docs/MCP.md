# MCP tools

Daguerre's Hoard exposes 9 tools over stdio (`daguerre_hoard/mcp_server.py`, a
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
    "daguerre": {
      "command": "C:/path/to/daguerres-hoard/.venv/Scripts/python.exe",
      "args": ["C:/path/to/daguerres-hoard/daguerre_hoard/mcp_server.py"],
      "env": { "DAGUERRE_URL": "http://127.0.0.1:8814" }
    }
  }
}
```

`DAGUERRE_URL` must be an `http://` loopback address (`127.0.0.1` or
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
- Agent results never carry `thumbnail_url` (a relative URL no agent can
  fetch); the UI's own routes keep it for rendering.
- `photos_search`/`photos_similar` return `returned` (this call) and
  `indexed_total` (every ranked photo that passed the filters, not a match
  count -- ranking is by similarity, never a filter) plus a per-result
  `relevance` band (`strong`/`medium`/`weak`, calibrated per embedder);
  trust `relevance` over the raw `score`. `contact_sheet` defaults to
  `false` -- set it, or call `photos_show`, only when you can see images.

| tool | read-only | idempotent | purpose |
| --- | --- | --- | --- |
| `photos_search` | yes | yes | text (English) -> photos; contact sheet only on request |
| `photos_similar` | yes | yes | photos that look like a given photo |
| `photos_show` | yes | yes | up to 4 images for close inspection |
| `photos_describe` | yes* | yes | EXIF, place, path; optional local caption |
| `photos_duplicates` | yes | yes | exact / near duplicate groups + keeper |
| `photos_timeline` | yes | yes | counts per year/month, on this day |
| `photos_library` | yes | yes | folders, counts, model, running jobs |
| `photos_add_folder` | no (adds) | yes | register a folder and index it |
| `photos_album` | no (adds) | yes | create or extend an album |

\* `photos_describe(caption=true)` stores the generated caption in Daguerre's
own database (the photo file is never touched). All annotations set
`destructiveHint=false` and `openWorldHint=false`.

## photos_search

| param | type | default | notes |
| --- | --- | --- | --- |
| `query` | string | none | describe the photo **in English**; leave empty (with filters) for a plain chronological listing |
| `taken_after` / `taken_before` | ISO date or datetime | none | inclusive; a plain date covers the whole day |
| `year` | int | none | 1800-2200 |
| `month` | int | none | 1-12 |
| `place` | string | none | substring of the place, the city it belongs to ("Lisbon" finds Alfama and Restelo) or the country |
| `folder` | string | none | substring of the path, either slash direction |
| `camera` | string | none | substring of make or model |
| `orientation` | `"landscape"` or `"portrait"` | none | |
| `min_megapixels` | float | none | |
| `has_gps` | bool | none | `false` finds photos without GPS |
| `limit` | int | 12 | 1-50 (a higher value is clamped; `limit_clamped`/`requested_limit` say so) |
| `offset` | int | 0 | page past the first `limit` results |
| `min_score` | float | none | drop results below this cosine score |
| `contact_sheet` | bool | false | set `true`, or call `photos_show`, only if you can see images |

Returns
`{query, returned, indexed_total, has_more, next_offset?, embedder, results: [{n, id, path, taken_at, place, size, width, height, score, relevance, caption_match?}], note?}`
and, only when `contact_sheet=true`, one JPEG `ImageContent` (5 columns, at
most 20 cells, at most 200 KB). `indexed_total` is every ranked photo that
passed the filters, not a match count. `relevance` is `strong`/`medium`/
`weak`, calibrated per embedder (the colour fallback never returns
`strong`); a top-level `note` flags things like no strong match, a
non-English query, or filters that excluded every photo (naming the one
filter whose removal alone brings photos back, e.g. `without
min_megapixels=2 alone, 40 would`). There is no bare `count` in agent
results: a model quoted it as "I found 87 photos". When `query` is
empty and filters are given, the result is a plain chronological listing
(`mode: "filtered_listing"`, no `score`/`relevance`) instead of a ranked
search. When captions exist, ranking is hybrid: 0.8 x normalised cosine +
0.2 x normalised BM25 over the captions (`caption_match: true` marks those
hits).

Bad input is an error the model can fix, e.g.
`invalid_argument: unknown filter(s): city. Valid filters: taken_after, ...`
or `invalid_argument: month must be 1-12, got 13`.

## photos_similar

`photo_id` (preferred) or `path` (absolute), `limit` (1-50, default 12),
`offset` (default 0), `min_score` (none), `contact_sheet` (default
**false** -- set it, or call `photos_show`, only if you can see images).
Returns `{photo_id, returned, indexed_total, has_more, next_offset?,
embedder, results: [{..., relevance}]}` with the photo itself excluded,
plus a contact sheet only when requested.

## photos_show

`ids` (list; first 4 distinct ids used), `size` (128-1024, default 768,
long side in pixels). Returns `{shown: [{id, path, taken_at}], not_found:
[...], unreadable?: [...], ignored_ids?: [...]}` followed by one JPEG per
shown photo, each at most 200 KB (quality, then size, is lowered to fit).
EXIF rotation is applied.

## photos_describe

`photo_id` (required), `caption` (default false). Returns `{id, path,
taken_at, date_source, place, size, width, height, make,
model, lens, f_number, exposure_time, iso, focal_length, orientation,
gps_lat, gps_lon, city, region, country, caption}`; fields without data
are omitted. `date_source` is `exif` or `file_mtime` (no EXIF date). With
`caption=true` and no caption yet, the photo (downscaled to 1024 px) is
sent to whatever the shared model backend resolves for the `vision`
capability (Faustus, a loopback Ollama/llama.cpp/OpenAI-compatible
server, or the app's own configured Ollama override -- see the README's
"Shared models" section); if nothing resolves the result carries
`caption_error` instead of failing the call.

## photos_duplicates

`kind` (`"exact"` default, or `"near"`), `limit` (1-50 groups, default
10), `include_ids` (default false). Returns `{kind, count, total_groups,
has_more, reclaimable_bytes_total, note?, groups: [{kind, keeper_id, keeper_path,
count, max_distance, reclaimable_bytes, other_paths (up to 3),
more_paths?, photo_ids? (only with include_ids=true)}]}`, groups with the
most wasted space first. Each group is summarised (not every member's
full record) to fit a small context; set `include_ids=true` only when you
need every photo's id (e.g. to build an album from a group). Exact =
identical BLAKE2b content hash; near = perceptual hash (pHash) within
Hamming distance 6, grouped with union-find (pure exact-copy groups are
left to `kind="exact"`). Keeper: largest resolution, then oldest
`taken_at`, then earliest file time, away from a folder that looks like a
backup/copy/WhatsApp, then shortest path. Daguerre never deletes anything.
A near group can join different photos that look alike (several scans of
one album, receipts), so `kind="near"` carries a `note` saying its bytes
are an upper bound and the owner must check each group before deleting.

## photos_timeline

`year` (optional). Without it: `{years: {"2024": 812}, months: {"2024":
{"03": 40}}, on_this_day: [{id, taken_at, place}],
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

`path` (absolute, existing folder, not inside Daguerre's data folder).
Registers the root (or finds the existing one) and starts an index job.
Returns `{root: {id, path, photo_count}, job_id, next}`. There is no tool
to remove a folder: that is a human action in Settings.

## photos_album

`name` (1-100 characters, matched case- and accent-insensitively), `photo_ids` (up to
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
| `daguerre_unavailable` | the app is not running: "Start it from Faustus (Apps) or with 'Iniciar Daguerre.cmd', then retry." |
| `daguerre_timeout` | no answer within 120 s (a big scan may be running); retry once |

## Limits

Default result sizes are 10-12 items, at most 50; contact sheets show at
most 20 photos and weigh at most 200 KB; `photos_show` returns at most 4
images of at most 200 KB each. Vector search is brute-force cosine over a
memory-mapped float32 matrix, fine to about 200k photos.

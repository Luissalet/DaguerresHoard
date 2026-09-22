# Architecture

## Modules (`daguerre_hoard/`)

- `config.py` -- paths, port, supported extensions. One `Settings`
  dataclass; only the two entry points (`__main__.py`, `mcp_server.py`)
  read environment variables.
- `db.py` -- SQLite schema (stdlib `sqlite3`, WAL), in-place migrations
  for databases created by older builds, and `ThreadLocalConnections`:
  one connection per thread.
- `scanning.py` -- the `os.scandir` walker: stable order, skips
  dot-folders, Windows Hidden/System folders, symlinked folders and
  junctions, known system folders, files under 8 KB, excluded globs, and
  Daguerre's own data folders.
- `formats.py` -- registers `pillow-heif` when installed so HEIC/HEIF
  decode everywhere; without it those extensions are not listed at all.
- `hashing.py` -- streamed BLAKE2b content hash.
- `metadata.py` -- EXIF with Pillow: IFD0 (make, model, orientation), the
  Exif sub-IFD (DateTimeOriginal + OffsetTimeOriginal, exposure, ISO,
  focal length, lens) and the GPS IFD (DMS -> signed decimal). Tuple
  values, zeroed dates and 0,0 fixes are handled. `taken_at` falls back to
  the file time with `date_source = "file_mtime"`.
- `thumbnails.py` -- EXIF-rotated WebP thumbnails, JPEG `draft()` decode,
  512 px long side, q80, `data/thumbs/<id[:2]>/<id>.webp`.
- `phash.py` -- 64-bit pHash and an exact multi-index near-duplicate
  lookup (below), plus union-find.
- `duplicates.py` -- exact and near groups and the keeper rule.
- `embeddings.py` -- the `Embedder` protocol; `FakeEmbedder` (colour
  histogram, deterministic across processes); `ClipEmbedder` (fastembed /
  ONNX Runtime CLIP ViT-B/32, 512-d, no PyTorch); `VectorStore`.
- `geocode.py` -- offline reverse geocoding: bundled 10-city fixture, or
  GeoNames `cities1000` once the user downloads it. With `cities1000` a
  neighbourhood's `region` is the city it belongs to, read from the admin
  codes; `GEOCODER_VERSION` is stamped in settings so a library labelled
  by an older version is relabelled once at start.
- `captions.py` -- `LinkCaptioner` (what `Library._captioner()` returns:
  captions through Hoard Link's `vision` capability) plus the original
  `OllamaCaptioner` (a direct connection to one Ollama server, kept for
  standalone use and exercised by its own tests); both downscale to
  1024 px, and the shared helper bypasses system proxies for loopback.
- `backend.py` -- `Backend`: builds the vendored Hoard Link `Link` from
  `data/backend.json` plus environment overrides, and maps the legacy
  `ollama_base_url`/`ollama_model` settings into the `vision` capability's
  explicit override once the owner has actually saved one. See "Shared
  model backend" below.
- `lang.py` -- a dependency-free stopword heuristic (`detect_non_english`)
  that decides whether the UI should offer to translate a search query.
- `hoard_link/` -- vendored copy of the shared Hoard Link library (never
  edited; see `VENDORED.txt`).
- `contact_sheet.py` -- numbered JPEG grid (at most 20 cells, 200 KB) and
  the shared "encode JPEG under N bytes" helper.
- `jobs.py` -- `JobManager` / `JobHandle`: a daemon thread per job,
  progress and stats in the `jobs` table.
- `library.py` -- the engine (no FastAPI import): indexing pipeline and
  every operation the UI and the agent use.
- `api.py` -- FastAPI app: guard middleware, UI routes, audited
  `/api/agent/<tool>` routes, flat `{error, message}` errors, static
  files confined to `frontend/dist`.
- `guard.py` -- DNS-rebinding and cross-site write guard.
- `mcp_server.py` -- standalone stdio adapter (stdlib + httpx + mcp).
- `demo.py` -- synthetic demo library for `--demo`.

## Data model

`data/daguerre.db` (SQLite, WAL): `roots`, `photos` (one row per file; `id`
is a random 32-hex id that survives moves), `photos_fts` (FTS5 over
captions), `albums` / `album_photos`, `jobs`, `agent_calls`, `settings`.
Vectors live in `data/vectors.f32`, a float32 matrix addressed by
`photos.embed_row`; `photos.embed_model` records which embedder wrote the
vector, and search only compares vectors of the active model. The CLIP
cache is `data/models`, GeoNames data `data/geodata`, logs
`data/logs/app.log` (rotating).

## Indexing pipeline

`Library._run_index`, in a job thread. Index runs are serialised by a
lock: a second request waits for the first instead of racing it.

1. Walk every registered root (`walk_images`). An unreachable root is
   reported in the job stats and its photos are left alone.
2. In chunks of 64 files:
   - stat each file; same `(size, mtime_ns)` as the stored row -> skip
     without reading it (incremental rescans cost one `stat` per file);
   - stream-hash the rest in a thread pool;
   - same hash as the stored row -> refresh size/mtime only; same hash as
     a row whose file no longer exists -> a moved or renamed file: update
     the path, keep the id, vector, caption and album memberships;
   - otherwise, in the thread pool (Pillow releases the GIL): EXIF,
     thumbnail, pHash; then write the row on the job thread. New content
     at a known path keeps the id but drops the old caption.
   - any exception is recorded for that file (count + first five
     messages in the job stats) and the scan continues.
3. Embed new, changed and stale photos from their thumbnails, 32 at a
   time. "Stale" = no vector, or a vector from another embedder (for
   example photos indexed before the CLIP model was downloaded).
4. Rows under reachable roots whose file vanished (and was not found as
   moved) are flagged `missing` -- hidden, never deleted, so an unplugged
   drive does not lose albums or captions.

Progress (files/s and ETA) and stats are written to the job row and
polled by the UI. Jobs still `running` when the process stopped are
marked `interrupted` on the next start.

Daguerre never opens an original for writing and never renames, moves or
deletes anything under a root; all writes go to the data folder. Tested
by `test_full_index_preserves_original_files`.

## Near duplicates: exact multi-index lookup

The 64-bit pHash is split into four 16-bit chunks with one bucket table
each. If two hashes differ in at most `t` bits, at least one chunk
differs in at most `floor(t/4)` bits (pigeonhole), so probing every chunk
with its exact value and every value within `floor(t/4)` flipped bits
(17 probes per chunk for `t = 6`) finds every true neighbour. Candidates
are confirmed with a real Hamming distance, then joined with union-find.
`test_chunk_index_is_exact_without_brute_force_fallback` checks this on
8,000 random hashes with planted 2+2+1+1 neighbours against brute force.

## Search

Filters become one SQL `WHERE` clause (validated first: unknown names and
bad values are errors that list what is accepted). The query text is
embedded once and scored against the filtered rows' vectors with one
matrix product (brute force; fine to about 200k photos). If captions
exist, the rank is `0.8 * cosine_norm + 0.2 * bm25_norm`; the reported
`score` is always the raw cosine.

## Threads and processes

One process. uvicorn's thread pool serves the sync routes; each job runs
in its own daemon thread, and the index job uses a small thread pool for
hashing and decoding. Every thread has its own SQLite connection (WAL,
10 s busy timeout), so transactions never interleave. The vector store is
guarded by a lock; it grows by closing the mapping, extending the file
and re-mapping (Windows cannot replace a mapped file). The CLIP model is
a per-cache-directory singleton, loaded once per process with
`local_files_only` at start-up; downloading is an explicit user action
(`/api/model/download`), after which the library is re-embedded.

No `multiprocessing`, no subprocesses except `explorer /select,` on
Windows for "Open in Explorer".

## HTTP surface

- `/api/health` -- `{service: "daguerres-hoard", name, version, status,
  photo_count, roots, embedder}`.
- `/api/agent/<tool>` -- the nine MCP tools, audited in `agent_calls`.
- UI routes (not audited): `/api/photos`, `/api/photos/{id}`,
  `/thumbnail`, `/preview` (large JPEG of the original, EXIF-rotated,
  also for HEIC/TIFF), `/open`, `/caption`, `/api/search` (auto-translates
  a non-English query -- see "Shared model backend" below), `/api/similar`,
  `/api/duplicates`, `/api/timeline`, `/api/places`, `/api/roots`,
  `/api/scan`, `/api/jobs`, `/api/albums`, `/api/settings`, `/api/model`,
  `/api/geocoder/download`, `/api/captions/batch`, `/api/agent-calls`,
  `/api/backend` (GET: Hoard Link's resolution for every capability plus
  the local CLIP status), `/api/backend/config` (PUT: Faustus URL/token
  and per-capability overrides, persisted to `data/backend.json`; the
  token is never read back), `/api/backend/recheck` (POST: rebuilds the
  `Link`, which also clears its 30 s probe cache).
- Guard: requests whose `Host` is not `127.0.0.1:<port>` or
  `localhost:<port>` get 403; non-GET requests with a foreign `Origin` or
  `Sec-Fetch-Site: cross-site` get 403. No CORS headers.
- Static files: only files whose resolved path is inside `frontend/dist`;
  every other non-API path gets `index.html`.

## Shared model backend (Hoard Link)

Daguerre uses two of Hoard Link's eight capabilities: `vision` (captions) and
`llm` (UI-only query translation). `Library.backend` is one
`daguerre_hoard.backend.Backend`, built once in `Library.__init__` and
rebuilt (`backend.reload()`) whenever `data/backend.json` changes or the
legacy Ollama settings are saved. `Backend._build_link()` loads
`LinkConfig` from `data/backend.json` + environment, then -- only when
that file sets no explicit `vision` override *and* a row for
`ollama_base_url` actually exists in the `settings` table (a fresh install
has neither) -- maps the legacy value into `vision`'s explicit
`CapabilityConfig`. This is a one-way migration path, not a permanent
coupling: setting a `vision` override in `data/backend.json` (via
`PUT /api/backend/config`) always wins over the legacy field.

`Library._captioner()` -- the seam `tests/test_engine_edge_cases.py` and
`tests/test_caption_batch.py` monkeypatch -- returns a `LinkCaptioner`
wrapping `self.backend.link`. It calls
`link.sync.chat(images=[jpeg], capability="vision")`, so a caption is
served by whatever resolves: the legacy/explicit Ollama address, a running
Faustus, or a loopback probe -- never a private, Ollama-only connection.
`start_caption_batch` calls `link.sync.wait_idle("vision", max_wait_s=30)`
before every photo, so a background batch yields to whatever the owner is
doing with the shared model instead of racing it; if the model stays busy
for 20 rounds (~10 minutes) the batch postpones -- it stops, keeps what it
already captioned and reports the rest as `postponed` in its stats and job
message. The lightbox button and `photos_describe(caption=true)` are
foreground calls and never wait.

`Library.search_translated` (used only by the UI's `/api/search`, never
by `/api/agent/photos_search` -- the MCP tool's docstring tells the agent
to translate the query itself) runs `lang.detect_non_english` on the
query and, only when it looks confidently non-English, asks the `llm`
capability for a short English CLIP phrase via `link.sync.chat(...,
capability="llm")`. `Unavailable`/`BackendError` fall back silently to
searching with the original text and surface a `translate_error` field;
nothing ever blocks a search on the shared model being absent.

`Backend.reload()` (Re-check, saving overrides or the legacy Ollama
fields) builds a fresh `Link` -- an empty probe cache -- and closes the
replaced one after a 180 s grace period, longer than a chat call's
timeout, so an in-flight caption or translation finishes; each `Link`'s
sync facade owns a thread, an event loop and an HTTP client, so they are
never left behind. `LinkCaptioner` reads the current `Link` on every call,
so a running batch follows a reload. A `backend.json` that is not valid
JSON or has a malformed key does not stop the app: it falls back to
environment + automatic detection and reports `config_error`.

`GET /api/backend` returns `Backend.status()` (Hoard Link's `Resolution`
for all eight capabilities, `token_set`, the saved `overrides` without the
token, `config_error`, `used_capabilities`) plus
`image_search` (the local CLIP embedder's name and whether it is the real
model or the colour-only fallback) -- CLIP is never shared: it is not a
chat/embeddings-text model any of Hoard Link's capabilities cover.

## Key decisions

- **A thread and a SQLite table instead of a task queue.** One local user
  does not need more infrastructure.
- **Brute-force vector search.** A matrix product over 200k x 512 float32
  is a few hundred milliseconds; an ANN index can sit behind
  `VectorStore` later.
- **Fallback embedder until the model is downloaded.** The app and every
  default test work offline; the agent is told (a `note` in results) that
  the fallback only understands colours.
- **HTTP between the MCP adapter and the app.** The adapter needs nothing
  from the app's environment, and the same logic is tested through
  FastAPI's `TestClient`.
- **`link.sync.*`, never `await link.*`, from the FastAPI routes.** Every
  route in `api.py` is a plain `def`, matching the rest of the app (SQLite
  calls, `Library` methods); Hoard Link's synchronous facade runs its own
  event-loop thread instead of asking the whole app to become async for
  two capabilities.
- **A saved-row check, not just "is `vision` explicit", to migrate the
  legacy Ollama fields.** `get_setting(..., default=None)` distinguishes
  "the owner configured this" from "nothing was ever saved", so a fresh
  install benefits from Faustus/loopback resolution instead of being
  pinned to the built-in Ollama address forever.

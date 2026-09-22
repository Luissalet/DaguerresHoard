# Architecture

## Modules (`argus_hoard/`)

- `config.py` -- paths, port, supported extensions. One `Settings`
  dataclass; only the two entry points (`__main__.py`, `mcp_server.py`)
  read environment variables.
- `db.py` -- SQLite schema (stdlib `sqlite3`, WAL), in-place migrations
  for databases created by older builds, and `ThreadLocalConnections`:
  one connection per thread.
- `scanning.py` -- the `os.scandir` walker: stable order, skips
  dot-folders, Windows Hidden/System folders, symlinked folders and
  junctions, known system folders, files under 8 KB, excluded globs, and
  Argus's own data folders.
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
  GeoNames `cities1000` once the user downloads it.
- `captions.py` -- optional Ollama vision client (downscales to 1024 px,
  bypasses system proxies for a loopback Ollama).
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

`data/argus.db` (SQLite, WAL): `roots`, `photos` (one row per file; `id`
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

Argus never opens an original for writing and never renames, moves or
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

- `/api/health` -- `{service: "argus-hoard", name, version, status,
  photo_count, roots, embedder}`.
- `/api/agent/<tool>` -- the nine MCP tools, audited in `agent_calls`.
- UI routes (not audited): `/api/photos`, `/api/photos/{id}`,
  `/thumbnail`, `/preview` (large JPEG of the original, EXIF-rotated,
  also for HEIC/TIFF), `/open`, `/caption`, `/api/search`,
  `/api/similar`, `/api/duplicates`, `/api/timeline`, `/api/places`,
  `/api/roots`, `/api/scan`, `/api/jobs`, `/api/albums`,
  `/api/settings`, `/api/model`, `/api/geocoder/download`,
  `/api/captions/batch`, `/api/agent-calls`.
- Guard: requests whose `Host` is not `127.0.0.1:<port>` or
  `localhost:<port>` get 403; non-GET requests with a foreign `Origin` or
  `Sec-Fetch-Site: cross-site` get 403. No CORS headers.
- Static files: only files whose resolved path is inside `frontend/dist`;
  every other non-API path gets `index.html`.

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

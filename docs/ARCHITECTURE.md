# Architecture

## Modules (`argus_hoard/`)

- `config.py` -- paths, ports, supported extensions. One `Settings`
  dataclass; every other module takes a `Settings` or plain `Path`,
  never reads environment variables itself (except `__main__.py` and
  `mcp_server.py`, the two entry points).
- `db.py` -- SQLite schema (WAL mode, `stdlib sqlite3`) and a tiny
  key/value `settings` table for runtime config (Ollama URL/model).
- `hashing.py` -- streamed BLAKE2b content hash.
- `metadata.py` -- EXIF extraction with Pillow (dates, GPS DMS->decimal,
  camera fields, orientation).
- `thumbnails.py` -- EXIF-orientation-corrected WebP thumbnails, JPEG
  `draft()` fast decode, 512px long side.
- `phash.py` -- 64-bit perceptual hash + a chunked candidate index for
  near-duplicate lookup (see the note in that file on why the chunk
  index alone is a prune-only optimization, verified exact by brute
  force below ~5000 photos).
- `embeddings.py` -- the `Embedder` interface, `FakeEmbedder` (colour
  histogram, deterministic, used by tests and until the real model is
  downloaded), `ClipEmbedder` (fastembed/ONNX Runtime CLIP ViT-B/32,
  no PyTorch), and `VectorStore` (append-only memory-mapped float32
  matrix with brute-force cosine search -- documented fine to ~200k
  photos; a future version could add an ANN index without changing the
  interface).
- `geocode.py` -- offline reverse geocoding: a bundled 10-city fixture
  by default, or the full GeoNames `cities1000` dataset once
  downloaded (opt-in, `/api/geocoder/download`).
- `captions.py` -- optional Ollama vision client, off by default, never
  blocks indexing.
- `duplicates.py` -- exact (content hash) and near (pHash union-find)
  duplicate grouping with a keeper rule.
- `contact_sheet.py` -- numbered JPEG grid renderer, size-capped.
- `jobs.py` -- a `JobManager`/`JobHandle` pair: background work runs in
  a daemon thread, progress is written to the `jobs` table and polled
  by the UI (`/api/jobs`). No task queue, no external dependency --
  indexing a personal photo folder does not need one.
- `scanning.py` -- pure filesystem walk + change-detection helpers
  (`(size, mtime_ns)` signature), used by `library.py`'s pipeline.
- `library.py` -- the engine: everything in one place that is not
  transport (no FastAPI import). `Library` owns the DB connection, the
  embedder, the vector store, the geocoder and the job manager, and
  implements the indexing pipeline plus every read/write operation the
  API and MCP adapter expose. This is what `tests/test_library.py`
  exercises directly.
- `api.py` -- FastAPI app: the guard middleware, UI-facing routes, and
  `/api/agent/<tool>` (thin wrappers around `Library` methods with
  agent-call logging).
- `guard.py` -- the browser-attack guard (Host header / Origin /
  Sec-Fetch-Site checks), independent of FastAPI's routing so it is
  easy to unit test.
- `mcp_server.py` -- standalone stdio adapter (stdlib + httpx + mcp
  only). Talks to the running app over HTTP, exactly like any other
  client of `/api/agent/*`.
- `demo.py` -- synthetic demo photo generator (`--demo`).

## Data model

SQLite, one file (`data/argus.db`), WAL mode. Tables: `roots`, `photos`
(one row per registered file; `id` is a UUID stable across moves/renames),
`photos_fts` (FTS5, captions only, contentless), `albums`/`album_photos`,
`jobs`, `agent_calls`, `settings`. Vectors live outside SQLite in
`data/vectors.f32`, a flat float32 matrix; `photos.embed_row` is the row
index into it. Thumbnails are WebP files under `data/thumbs/<id[:2]>/`.

## Indexing pipeline

`Library._run_index` (background thread via `JobManager`):

1. Walk every registered root (`scanning.walk_images`), skip hidden/
   system folders, unsupported extensions, and files under 8 KB.
2. For each file: compare `(size, mtime_ns)` against the DB row for
   that path. Unchanged -> skip without hashing (this is what makes
   incremental rescans fast and is directly tested).
3. If different (or new), hash the content. If the hash matches an
   existing row whose old path no longer exists on disk, treat it as a
   **moved/renamed file**: update the path, keep the id, embedding and
   thumbnail. Otherwise extract metadata, build the thumbnail, compute
   the pHash, reverse-geocode GPS if present, and upsert the row.
4. Once every file in the batch has been processed, embed every new/
   changed thumbnail in batches of 32 (`Library._store_embedding`),
   which is the expensive step and the reason it is batched separately
   from the per-file metadata work.
5. Any previously-indexed file under a scanned root whose path was not
   seen this walk and no longer exists on disk is marked `missing`
   (hidden from the grid, not deleted from the index -- Argus never
   guesses that a file is gone forever).

Argus never opens a source file for writing and never calls `os.remove`,
`os.rename` or `shutil.move` on anything under a registered root -- the
only filesystem writes are inside `data/`. This is a tested invariant
(`test_full_index_preserves_original_files`).

## Threads and processes

One process, one background daemon thread per running job (indexing,
GeoNames download). SQLite connections are created with
`check_same_thread=False` and used from both the request thread and job
threads; WAL mode plus a 5s busy timeout keep that safe for a
single-writer, low-concurrency desktop app. The embedder is a
module-level singleton per model-cache directory so a real CLIP model is
never loaded twice in the same process.

## Key decisions

- **No task queue / no Celery / no Redis.** A thread + a SQLite table is
  enough for a single local user; adding infrastructure here would be
  the wrong kind of complexity for what this is.
- **Brute-force vector search, not an ANN index.** Documented as fine to
  ~200k photos (a numpy matmul over that many 512-d float32 vectors is
  a few hundred ms); an ANN index is an obvious extension point behind
  the same `VectorStore` interface if a user's library grows past that.
- **FakeEmbedder as the default until CLIP is cached.** Keeps the app
  fully functional offline on first run and keeps every test free of
  network access and a ~350 MB download, while still exercising the
  exact same search/embedding code paths as production.
- **HTTP between the MCP adapter and the app**, not a shared Python
  process. This is what the contract asks for (the same `/api/agent/*`
  logic testable via FastAPI's `TestClient`), and it also means the
  adapter has no dependency on the app's Python environment beyond
  `httpx` and `mcp`.

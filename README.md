# Argus's Hoard

### Do you have the photo of the dog on the beach from last summer?

**A local, private photo library that understands what is in your pictures -- and hands the answer to a local AI model as data it can act on, not a folder it cannot see.**

[Español](README.es.md) · [Run locally](#run-locally-on-windows) · [Connect an AI](docs/MCP.md) · [Portfolio](https://luissalet.github.io/Portfolio/#projects)

![Argus's Hoard library grid, demo data](docs/media/library.png)
*Actual application, synthetic demo data (generated gradients, not real photos).*

## Why

A local assistant can read files and answer questions about text, but it
cannot look at a folder of 20,000 photos and tell you which one has the
whiteboard notes from March, or whether you already have three copies of
the same trip photo taking up space. Argus indexes the owner's photo
folders locally -- CLIP embeddings via ONNX Runtime, no PyTorch, no cloud
call -- extracts EXIF and reverse-geocodes GPS offline, finds exact and
near duplicates, and hands a model compact, filtered results plus a single
numbered contact-sheet image so a vision-capable model can look at ten
candidates for the price of one. Argus never modifies, moves or deletes an
original file; that is a hard invariant, and it is tested.

## What is implemented

| Area | Available now | Boundary |
| --- | --- | --- |
| Indexing | Incremental scan, change detection by size+mtime, moved/renamed files keep their id, EXIF (dates, GPS, camera), WebP thumbnails, background job with progress | No file-watcher (rescans are manual/on-demand, not automatic on file-system events) |
| Search | CLIP text->image search (`FakeEmbedder` fallback before the ~350MB model is downloaded), filters (date, place, folder, camera, orientation, GPS), hybrid with captions when present | English queries work best with CLIP; the tools tell the model to translate first |
| Duplicates | Exact (content hash) and near (perceptual hash, chunked candidate index verified against brute force) grouping with a keeper suggestion | Read-only by design -- Argus never deletes; "Copy paths" is the closest it gets to cleanup |
| Places | Offline reverse geocoding (bundled 10-city fixture, or the full GeoNames `cities1000` on demand) | No map tiles (no external network for a view); country/city grouping only |
| Captions | Optional local Ollama vision model, off by default, written into an FTS index for hybrid search | Never generated automatically; only on request per photo or a batch job |
| Albums | Agent- and human-created collections, non-destructive | No nested albums |
| Assistant integration | `faustus-plugin.json`, 9 MCP tools over stdio, every agent call audited in "Assistant activity" | `photos_add_folder` can only add a root; removing one is a human-only UI action |

## Connect it to Faustus

Argus declares itself with `faustus-plugin.json`. Start the app, then in
Faustus: **Connectors -> Nearby apps -> Add**.

It also works with any MCP client over stdio:

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

| Tool | What | Read-only? |
| --- | --- | --- |
| `photos_search` | Text -> photos, with filters and a contact sheet | yes |
| `photos_similar` | Visually similar photos | yes |
| `photos_show` | Up to 4 full images for the model to look at | yes |
| `photos_describe` | EXIF, place, path, optional caption | mostly (caption write only) |
| `photos_duplicates` | Exact/near duplicate groups + keeper | yes |
| `photos_timeline` | Counts per year/month, "on this day" | yes |
| `photos_library` | Roots, counts, model/job status | yes |
| `photos_add_folder` | Register a new root and index it | adds only |
| `photos_album` | Create/extend an album | adds only |

Full argument/output reference: [docs/MCP.md](docs/MCP.md).

## Run locally on Windows

Double-click **`Iniciar Argus.cmd`**, or from PowerShell:

```powershell
./scripts/start.ps1              # first run: creates .venv, installs, builds the UI
./scripts/start.ps1 -Demo        # same, with synthetic demo data
./scripts/stop.ps1
```

Manual steps:

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements-lock.txt
.venv\Scripts\pip install --no-deps -e .
cd frontend; npm ci; npm run build; cd ..
.venv\Scripts\python -m argus_hoard --demo
```

`--demo` uses `data-demo/` (synthetic photos, generated fresh) instead of
`data/`, so you can try Argus without pointing it at real files.

## Architecture

FastAPI + SQLite (WAL) core, React 19 + Vite frontend, a standalone MCP
stdio adapter. Details, data model and the indexing pipeline:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tests

```
pytest -q      # 37 tests, ~3.5s, no network
```

Covers: EXIF/GPS extraction and orientation, thumbnailing, perceptual-hash
near-duplicate grouping (chunk index verified against brute force),
exact/near duplicate keeper selection, contact-sheet size/byte caps, the
deterministic `FakeEmbedder` search ranking, the vector store's grow/
persist behaviour, offline reverse geocoding, a mocked Ollama caption
client, the `faustus-plugin.json` manifest, the full indexing pipeline
(original files untouched, incremental rescan skips unchanged files,
moved files keep their id), the HTTP API including the browser-attack
guard, and a real MCP protocol round trip over stdio against a live,
indexed instance of the app.

## Privacy and limits

Everything runs on `127.0.0.1`; no telemetry, no network call the UI
does not explicitly say it is making (the CLIP model download and the
optional GeoNames dataset are the only two, both opt-in and visible in
Settings). Vector search is brute-force cosine, documented fine to
around 200k photos on a single machine; a larger library would want an
ANN index behind the same `VectorStore` interface.

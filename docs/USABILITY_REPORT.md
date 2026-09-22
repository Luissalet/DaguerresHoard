# Usability report

First real use of Argus's Hoard, as a person in the browser and as an
agent over MCP, following the eight scenarios in
[USE_CASES.md](USE_CASES.md). This pass records what happened. It fixes
nothing: none of the problems stopped the walkthrough. Every finding has
the fix it needs; the next pass makes them.

## Second pass: fixes

Every blocker is fixed, each with a regression test. pytest went from
116 to 132 (`pytest -q`); `npm run build`, the MCP protocol test
(`tests/test_mcp_protocol.py`) and the manifest test
(`tests/test_manifest.py`) stay green. Each fix was also exercised live:
the app running on a free port (demo data), agent calls over real HTTP
(`curl`), and the UI driven with Playwright (screenshots in
`data-uxtest/shots/`, gitignored) with zero console errors.

| Finding | Commit | What changed |
| --- | --- | --- |
| B1 | `4a5956d` | `contact_sheet` defaults to `false` everywhere (Library, HTTP bodies, MCP signatures); `photos_show`'s description and the FastMCP instructions now say "only if you can see images", for both kinds of model. |
| B2 | `4a5956d` | `count` (misleading: every ranked photo) is joined by `returned` + `indexed_total`, kept as an alias so nothing existing breaks; a per-result `relevance` band (strong/medium/weak) replaces trusting the raw `score`. |
| B3 | `4a5956d` | The colour fallback's relevance bands never reach "strong", and a query with no colour word is `weak` across the board with a note that the order is arbitrary. |
| B4 | `4124d4e` | `ReverseGeocoder` also finds the nearest big place (capital/admin centre or population >= 15,000) and stores it as `region`, so `place="Lisbon"` matches a neighbourhood again. |
| B5 | `4a5956d` | `offset`/`next_offset` page a search past 50 results; `query` is optional when filters are given (a plain chronological listing); a clamped `limit` says so. |
| A2 | `78f3176` | Exact-duplicate keeper tie-break also prefers the earliest file mtime and a non-backup-looking folder before path length; "Copy paths" excludes the keeper; tiles show the parent folder. |
| A4 | `2a02d6f` | Agent results never carry `thumbnail_url`; `photos_duplicates` groups are summarised by default, with `include_ids` for when an agent needs every id. |
| A6 | `fe91943` | The open-album view gained a "Select photos" mode and a "Remove N photos" action with the two-step inline confirmation AGENTS.md requires. |
| A7 | `4a5956d` | `add_root` strips surrounding quotes (Explorer's "Copy as path"). |
| A8 | `4a5956d` | Album names match accent-insensitively (NFKD fold before the case-insensitive compare). |
| A9 | `4a5956d` | An agent search whose query looks non-English gets a note to translate and retry. |
| A10 | `4a5956d` | An empty result now says when the filters excluded everything, or when `min_score` did. |
| A11 | `4124d4e` | Beyond `geocode.NEARBY_KM` (50 km) the bundled 10-city fixture reports no place rather than a wrong one; cities1000 keeps the country, flagged `approximate`; the Places page suggests the world-cities download when any exist. |

### Left for a later pass, and why

- **A1** (CLIP download is not the obvious first step). Needs a first-run
  checklist component reused across Library and Search plus a redesigned
  Settings layout (move the Image model card first, MB-based progress).
  That is more surface area than the other fixes here touch safely in one
  pass without a dedicated design review; the existing amber "Content
  search is not available yet" banner and Settings badge still work.
- **A3** (near-duplicate groups chain unrelated photos, "44.9 MB" reads as
  exact). The fix (bound a group's diameter with complete linkage or a
  keeper-centered star, skip mismatched aspect ratios unless one is a
  rotation, confirm with CLIP cosine ~0.95+ when available) changes the
  grouping algorithm itself and needs re-validation against real photos,
  which this synthetic set cannot give ("my drawn images collide more
  than real photos would" -- original report). Wording it as "up to N MB"
  and showing each group's distance is a smaller, safe follow-up.
- **A5** (exact copies appear side by side in search/albums). Needs a
  `content_hash`-based collapse applied consistently to `search`,
  `similar` and albums; deferred to keep this pass's diff reviewable, and
  because A2's keeper fix already changes which copy a person sees.
- **C1-C7** (cosmetic copy/UI). None block or mislead a decision the way
  the blockers and A1-A11 do; left for a pass that also retakes the
  screenshots this report describes, since C4/C5/C7 are visual layout
  issues best judged from a fresh screenshot pass, not guessed at.

Not re-verified in this pass: real Faustus with a text-only 27B model
(B1 is fixed at the MCP/HTTP level, where it was reproduced), Windows-only
paths and `.ps1` scripts, captions/query translation (no vision/LLM
server), CLIP thresholds and near-duplicate false positives on real
photos, and libraries above the synthetic set's 262 photos -- the same
list the first pass left, since fixing the reproducible bugs did not
require any of them.

## Third pass: re-walk after the fixes

Every use case was walked again, as a person (Playwright at 1280x800 and
1920x1080, Spanish and English, light and dark, every screenshot read) and
as an agent (`scripts/agent_walkthrough.py` over real MCP stdio), against
three instances: a **fresh** first run (empty data folder, folder added
through the UI with Explorer-style quotes, the image model downloaded from
Settings), an **upgraded** library (the first pass's data, labelled by the
old geocoder with the world-cities file, now opened with the new code),
and the `--demo` data for the README screenshots. Zero console errors or
failed requests in every walk.

Two fixes of the second pass did not survive contact with real data:

- **B4 was not fixed.** On the real `cities1000` file the "nearest place
  of 15,000+ people" is often another neighbourhood: Alfama became
  "Alfama, Sao Jorge de Arroios", Madrid's districts got no parent, and
  `place="Lisbon"` matched about 10 of the 54 trip photos. The unit test
  passed only because its fake file had no populous neighbourhoods. And an
  existing library never received the new labels at all: a rescan skips
  unchanged files, so the upgraded library still found 2 of 54.
- **B2 was half fixed.** Agent search results still carried `count` next
  to `returned` and `indexed_total` ("kept for older callers"), so a
  default search still said `count=262` to the model.

| Finding (re-walk) | Commit | What changed |
| --- | --- | --- |
| B4 on real data | `2f44ff8` | The parent city comes from the dataset's admin codes (the most populous seat of a division the place belongs to, within 30 km). Tested with real rows for Lisbon, Madrid, Tokyo, Kyoto and Cadiz. |
| B4/A11 on existing libraries | `2f44ff8` | A geocoder-version stamp; a library labelled by another version is relabelled once in the background at start, and a photo that can no longer be placed loses its wrong label. |
| Places listed neighbourhoods | `2f44ff8` | 22 Madrid districts ("Ibiza", "Salamanca"), no "Madrid": Places now groups by the parent city (Tokyo 31, Kyoto 12, Lisbon 60, Madrid 92, Cadiz 13). |
| A11 hint never shown | `2f44ff8` | The bundled table returns no country beyond 50 km, so the "download the world data" hint counted zero; it now counts GPS photos without a city (25 on the fresh instance). |
| A1 download looked frozen | `2c5d4a2` | The first fresh download took more than ten minutes here at a static "5%". Progress is now reported in MB from the bytes on disk; the job ends with "image model ready: 262 photos analysed, content search is on". |
| B2 remnant | `6526a10` | Agent routes drop `count`. |
| A10 remnant | `6526a10` | An empty result names the filter to relax ("without min_megapixels=2 alone, 40 would"); UC5 recovered in one retry. |
| A3 wording | `6526a10`, `661e162` | Near-duplicate totals are an upper bound: a `note` for the agent, "up to ... check each group before deleting" in the UI. |
| A9 leaked into the UI | `6526a10`, `661e162` | The agent's English translate hint showed verbatim in the Spanish UI. Notes now carry codes and the UI words them in both languages. |
| Folder label "07" | `661e162` | Duplicate tiles climb past year/month folders ("Camera Roll/2024/07"). |
| Walkthrough out of date | `5be8ab0` | It crashed on the summarised duplicate groups; it now checks the new shapes. |
| Album prompt grammar | `80f2a45` | "The file stay where it is"; plus a test for the removal route. |

### Verdict per use case

| Use case | Verdict | Evidence |
| --- | --- | --- |
| UC1 first run | works, with a caveat | Quoted path accepted; 262 photos indexed, the truncated JPEG reported; model downloaded from Settings and re-embedded without further clicks; "sunset over the sea" finds sunsets. Caveat: the first-run checklist (A1's larger part) is still not built -- the amber badge and banner are the guide. |
| UC2 dog on the beach | works | UI and agent: burst + the two dog photos lead, all `strong`; no image in any default call; the Spanish query gets a translated hint in the UI and a named-language hint for the agent. |
| UC3 free up space | works, with a caveat | Exact: 15 groups, every keeper is the camera-roll original, "Copy paths of the extra copies" leaves it out. Near: the burst is one group and no chat-app copy is a keeper, but groups can still join different photos (six different scans); now labelled "up to" (A3's algorithm change is still open). |
| UC4 Lisboa 2024 album (agent) | works | Filters alone, two pages via `next_offset`: 54 of 54 trip photos on the bundled table, 53 of 54 with world cities (one GPS point jittered into the river lands in Trafaria, across it -- an honest label). |
| UC5 CV portrait (agent) | works, with a caveat | Empty first result names `min_megapixels`; the retry returns five real vertical portraits and an absolute path. Caveat: the synthetic portraits score `weak` (0.23-0.24), so the model is told to hedge; real photos need a threshold check. |
| UC6 short-film album | works | "film clapperboard" and "green screen studio" in March 2025: only clapperboards and green screens are `strong`; UI add-to-album folds accents; removing a photo in the album view works with the two-step prompt. |
| UC7 on this day (agent) | works | Three photos of 22 September (2023-2025) with Madrid places, no image. |
| UC8 places and receipts | works, with a caveat | Places is right on both geocoders, Cadiz is never labelled Portugal. The synthetic data has no receipts during the Lisbon trip, so "paper receipt" in July 2024 honestly says "no strong match"; without the date all 7 receipts come first. |

Agent walkthrough, final run: 28 calls, about 19k text tokens (35k in
the first pass), 2 images (both from `photos_show`, the only tool that
returns them), 0 failed checks, on both the fresh and the upgraded
instance. The tool list costs about 3.3k tokens (`photos_search` about
830 of them). pytest: 132 -> 141.

Still open: A1's first-run checklist, A3's grouping algorithm, A5
(copies side by side in results and albums: the WhatsApp copy of a dog
photo is still #2 for "dog on the beach"), C2/C3 (English reasons and
country names in the Spanish UI), C4-C7, and merging the two
"Rodaje La Estacion"/"Rodaje La Estación" albums the first pass created before
the accent fold.

## How it was tested

- **Data**: `scripts/make_uxtest_photos.py` built a synthetic `Pictures`
  folder of 268 files (103 MB) in `data-uxtest/`: a camera roll for
  2023-2025, a Lisbon trip with GPS and a +01:00 offset, a Tokyo/Kyoto trip
  (+09:00), a 12-frame burst of a dog on a beach, a Cádiz beach day, a
  short-film shoot (clapperboard, green screen), 18 WhatsApp copies with EXIF
  stripped, 15 byte-identical backup copies, PNG screenshots, TIFF scans,
  HEIC/WebP/GIF, a truncated JPEG, an empty file, an icon, a `.txt`, a
  `.dng` and a `._` resource fork. Every image is drawn with Pillow. The
  script also writes `photos_index.json`, which records the scene of each
  file, so every search result can be marked right or wrong.
- **Person**: the app ran on port 18840 with `--data-dir
  data-uxtest/app`, first with the colour fallback and then with the real
  CLIP model, downloaded through the UI. Playwright (Chromium) drove the UI
  at 1280x800 and 1920x1080, in English and Spanish, light and dark. I read
  every screenshot. The screenshots are in `data-uxtest/shots/` and are not
  committed. No page logged a console error or a failed request.
- **Agent**: `scripts/agent_walkthrough.py` spawns
  `argus_hoard/mcp_server.py` over stdio, the way Faustus does, and plays a
  small local model. It calls `list_tools`, chains the ids it gets back,
  checks each scenario against the data manifest and counts the images in
  every result. It ran against the fallback instance (16 failed checks) and
  the CLIP instance (12 failed checks). A second instance on port 18841
  stayed on the fallback so the scores of the two embedders could be
  calibrated side by side.

## What already works well

- Indexing is fast and robust. The first scan of 262 photos took about 14
  s on 2 CPUs and a rescan took 0.4 s. The truncated JPEG shows up as "1
  file could not be read" with the reason. Empty, tiny, dot-prefixed and
  unsupported files are skipped without noise. HEIC, TIFF, WebP and GIF are
  all indexed.
- The CLIP download took 24 s here (580 MB), and the library was
  re-embedded without any further clicks.
- CLIP search works. With CLIP, "dog on the beach" (summer 2024), "film
  clapperboard" and "green screen studio" (March 2025) put only correct
  photos in their top 5. "perro en la playa" also worked without
  translation.
- Agent errors say what to fix next: `month must be 1-12, got 13`, `Use an
  'id' value returned by photos_search`, `not an existing folder: ...`,
  `name is required: a short album title such as 'Lisbon 2024'`. When the
  app is down, the result is `argus_unavailable: ... Start it from Faustus
  (Apps) or with 'Iniciar Argus.cmd', then retry.`
- The timeline and "on this day" are correct: they show the three photos
  planted on 22 September.
- `photos_describe(caption=true)` with no vision model returns
  `caption_error` with the reason, not a failure.
- Keyboard use works: Tab reaches the sidebar with a visible focus ring,
  grid cells are buttons, and the lightbox handles the arrow keys, Escape
  and +/-. Dark mode reads well. Every piece of app copy is translated.

## Findings

Severity is how much each one hurts a real user: **blocker** (the user
cannot finish the scenario, or the tool breaks or misleads the model),
**annoying** (the user finishes with friction, or with a wrong result they
may not notice), **cosmetic**.

### Blockers

**B1. Search and similar return an image by default, and a text-only model's turn fails.** *(Live report, reproduced.)*
- **Scenario**: UC2, UC4, UC6 (agent).
- **What happened**: every default `photos_search` and `photos_similar`
  call returned one JPEG `ImageContent` of 50-150 KB, because
  `contact_sheet` defaults to `true` (all 8 default search calls in each
  run). On a Windows PC running Faustus with a text-only 27B model on
  llama.cpp, the next model call failed with HTTP 500 "image input is
  not supported" and the whole turn was lost. The server instructions and the skill make it worse: they tell
  every model to "look at the contact sheet before claiming", which a
  text-only model cannot do.
- **Fix**: default `contact_sheet` to `false` in `photos_search` and
  `photos_similar`, in the MCP signatures, the API bodies and the
  `Library` defaults. Its description should say "set true only if you can
  see images". The `photos_show` description must begin with "only if you
  can see images". Rewrite the FastMCP `instructions` and
  `skills/find-photos/SKILL.md` for both kinds of model: "If you can see
  images, ask for the contact sheet or photos_show; if not, rely on the
  relevance bands and say how sure you are." Add a protocol test that a
  default search result contains no image.

**B2. The result `count` reads as "N photos match".** *(Live report, reproduced.)*
- **Scenario**: UC2 (agent and UI).
- **What happened**: on the Windows PC the model answered 'I found 87
  photos that match "orange sunsets"'. Here, "orange sunsets" returned
  `count=262` (the whole library) and the summer "dog on the beach" search
  returned `count=76` (every photo in the date range). `count` is the number
  of ranked candidates: every embedded photo that passes the filters gets a
  rank, so the number says nothing about matches. The UI shows the same
  number as "50 photos / 262" ("50 fotos / 262" in Spanish).
- **Fix**: replace `count` with `returned` (results in this answer) and
  `indexed_total` (photos that passed the filters and were ranked). Give
  every result a `relevance` band (`strong` / `medium` / `weak`), calibrated
  per embedder (see "Relevance band calibration" below). Add a one-line
  `note`: "results are ranked by similarity, not filtered; use the
  relevance bands". Add an optional `min_score` parameter. Apply the same
  change to `photos_similar`. The UI label becomes "the best 50 of 262
  photos, ranked", and the grid can show the bands.

**B3. With the colour fallback, a query without a colour word returns noise with confident-looking scores.**
- **Scenario**: UC6 (agent) before the model download.
- **What happened**: `FakeEmbedder.embed_text` maps a query with no colour
  word to a seeded random vector. "film clapperboard", "a cat" and "paper
  receipt" all returned top scores of 0.28-0.35, the same range as a good
  CLIP match. The fallback run built the album "Rodaje La Estacion" out of a
  sunset, a cat and a forest, and those photos stay in it: the agent cannot
  remove photos, and neither can the UI (A6). The `note` does say that
  search only understands colours, which is good and must stay, but the
  numbers contradict it.
- **Fix**: fallback bands. A query with no colour word gets `weak` on every
  result, plus a note that says the order is arbitrary. A query with a
  colour word never gets better than `medium` (see the calibration below).
  The fallback never emits `strong`.

**B4. The GeoNames download, which the app itself suggests, breaks the `place` filter.**
- **Scenario**: UC4 and UC8.
- **What happened**: after "Download full world cities dataset", photos
  are labelled with the nearest `cities1000` entry, which is often a
  neighbourhood ("Restelo", "Graça", "Las Cortes", "Toranomon"), and
  `region` is empty. `place="Lisbon"` then matches 2 photos (74 before the
  download), and `place="Madrid"` and `place="Tokyo"` match 0. The skill
  tells the model to put places in `place`, so "make an album of the Lisbon
  trip" silently finds nothing. The labels mislead a person too: Madrid
  photos read "Ibiza, Spain" and "Salamanca, Spain" (both are Madrid
  districts, but they look like the island and the city).
- **Fix**: store the parent municipality or admin area next to the
  neighbourhood (GeoNames admin1/admin2 names, or the nearest
  PPLC/PPLA/PPLA2 or populated place of 15,000 or more). Match `place`
  against city, parent, region and country. Label as "Restelo, Lisbon,
  Portugal". Add a test that `place="Lisbon"` finds the same photos before
  and after the switch.

**B5. The agent cannot get more than 50 results, so "every photo of the trip" is impossible.**
- **Scenario**: UC4 (agent).
- **What happened**: `photos_search(place="Lisbon", year=2024, month=7,
  limit=50)` returned `has_more=true` (61 candidates), but the tool has no
  offset or cursor. `limit=100` was clamped to 50 without saying so. The
  album got 50 of 61 photos in one run. (The CLIP run "passed" only because
  the fallback run had already added a different 50.) The model also had to
  invent `query="photo"`, because a search needs a text query even when the
  owner only means "everything from that trip".
- **Fix**: add an `offset` parameter (with `next_offset` in the result).
  Make `query` optional when filters are given, and return a chronological
  listing in that case. When `limit` is clamped, say so in the result.

### Annoying

**A1. Downloading the CLIP model is not the obvious first step.** *(Live report.)*
- **Scenario**: UC1 (UI).
- **What happened**: the empty Library says only "Add a folder in
  Settings". After the scan, nothing points to the next step. The only
  signal is a small sidebar badge, "Content search is not available yet",
  which opens Settings. There, the technical Shared models card is the
  first thing in the grid and the Image model card sits beside it.
  Searching shows a clear amber banner, but only after a search. During the
  download, the header reads "Indexing... 5%", and the progress bar sits in
  the *folders* card at 5% until it is done: no MB counter. On a home
  connection, 600 MB at a static 5% looks frozen. The finished job reads
  "indexed 263 files: 0 new..." instead of "image model ready; 262 photos
  analysed".
- **Fix**: add a first-run checklist card on Library and Search, shown
  while anything is missing: (1) add a folder, (2) download the image model
  (about 600 MB, one click, with the button right there), (3) optional:
  world places. Show the same call to action in the post-scan state while
  the fallback is active. Move the Image model card first in Settings. Show
  download progress in MB, label the job "Downloading image model", and
  write a completion message that says what changed.

**A2. Exact duplicates: the backup copy is kept, and nothing on screen tells the copies apart.**
- **Scenario**: UC3 (UI and agent).
- **What happened**: in all 15 exact groups, the keeper is the copy in
  `Copia movil 2024`. The rule's last tie-break is the shortest path, and
  `Copia movil 2024/IMG_...` is shorter than `Camera Roll/2024/07/IMG_...`.
  The tiles show only file names, which are identical, so the folder is
  visible only in the hover title. "Copy paths" copies every path in the
  group, keeper included, so pasting the list into a delete command also
  deletes the keeper.
- **Fix**: show the parent folder on every tile. Make "Copy paths" copy only
  the extra copies, labelled "Copy paths of the extra copies", and let the
  owner mark a different keeper. Tie-break by the earliest file time, then
  away from folders whose names say backup/copy/WhatsApp ("copia", "backup",
  "WhatsApp"), then by path length.

**A3. Near duplicates chain different photos together and promise space that is not free to take.**
- **Scenario**: UC3 (UI and agent).
- **What happened**: union-find joined pairs within distance 6 into groups
  whose members were up to 14 bits apart. The result: 12 portraits of
  different people (landscape and portrait frames mixed), 8 different
  receipts, 6 different scans, 7 torii photos. The page says "44.9 MB would
  be freed by keeping one copy of each". The synthetic images are flat
  drawings, so pHash collides more often here than it would on real photos.
  But receipts, whiteboards and screenshots of one app are real-world
  look-alikes, and deleting "the extra copies" here loses real photos. The
  burst (12 frames plus its WhatsApp copies) and the WhatsApp copies were
  grouped correctly, and no WhatsApp copy was ever proposed as the keeper.
- **Fix**: limit a group's diameter (build a star around the keeper, or use
  complete linkage within the threshold). Never group photos with different
  aspect ratios unless one is the other rotated. When CLIP is active,
  confirm each pair with a cosine of about 0.95 or more. Word the near
  total as "up to" and show each group's distance.

**A4. Some agent results are too big for a small context.**
- **Scenario**: UC3 and UC4 (agent).
- **What happened**: `photos_duplicates(kind="near")` with its default
  `limit=10` returned 25.9k characters (about 8.6k tokens), because every
  photo of every group comes with its full record. `photos_search(limit=50)`
  returned about 6k tokens plus a 150 KB image. Every result also carries a
  relative `thumbnail_url` (about 60 characters) that no agent can use.
- **Fix**: summarise each duplicate group (keeper path, count, bytes, up to
  3 other paths, `photo_ids` on request). Drop `thumbnail_url` from agent
  results. Keep `path`: Faustus's file tools need it.

**A5. Search results and albums contain exact copies side by side.**
- **Scenario**: UC2 and UC4.
- **What happened**: the fallback "dog on the beach" run had the original
  and its backup at #1 and #2. The "Lisboa 2024" album holds burst frames
  from `Copia movil 2024` next to the originals.
- **Fix**: collapse results that share a `content_hash` into one, with
  `copies: n` and the keeper's id. The same rule deduplicates album
  additions.

**A6. A single photo cannot be removed from an album, even though the skill says the owner can.**
- **Scenario**: UC6 (UI), after B3.
- **What happened**: the album view has only "Delete album". The endpoint
  `/api/albums/{id}/remove` and `api.albumRemove` exist, but the UI never
  calls them. The skill tells the model "Removing ... album entries is for
  the owner, in the Argus UI", which is not possible today.
- **Fix**: add a remove control on each photo of an open album, and a
  select mode for several photos at once, with the two-step inline
  confirmation that AGENTS.md requires.

**A7. A path in quotes is rejected with a misleading message.**
- **Scenario**: UC1 (UI and agent).
- **What happened**: Windows Explorer's "Copy as path" puts quotes around
  the path. `"C:\...\Pictures"` got "path must be absolute (for example
  C:\Users\me\Pictures)". The path is absolute; only the quotes are wrong.
- **Fix**: strip surrounding whitespace and matching quotes before
  validating, in `Library.add_root`, which serves both the UI and the
  agent.

**A8. Album names match case-insensitively but not accent-insensitively.**
- **Scenario**: UC6.
- **What happened**: "Rodaje La Estación" (typed in the UI) and "Rodaje
  La Estacion" (from the agent) became two albums.
- **Fix**: fold accents when looking up an existing album (NFKD with the
  marks removed, then casefold), and keep the name as first typed.

**A9. An untranslated query gets no hint.**
- **Scenario**: UC2 (agent).
- **What happened**: `photos_search("perro en la playa")` got no hint,
  although `lang.detect_non_english` already exists. With CLIP it happened
  to work on common words; that is luck, not a guarantee.
- **Fix**: on the agent path, when the detector fires, add a note: "query
  looks Spanish; CLIP matches English far better, translate and retry". Do
  not auto-translate: the model can do that itself.

**A10. An empty result does not say whether the filters excluded everything.**
- **Scenario**: UC5 (agent).
- **What happened**: `orientation="portrait", min_megapixels=2` against
  1.9 MP portraits returned `count=0` and nothing else. The model cannot
  tell "no match" from "the filters are too strict".
- **Fix**: with B2's `indexed_total=0`, add a note: "no photo passes these
  filters", naming the filter that removed the most photos when that is
  cheap to compute.

**A11. The bundled 10-city geocoder puts photos in the wrong country.**
- **Scenario**: UC8.
- **What happened**: the Cádiz beach photos (about 450 km from the nearest
  bundled city) were labelled "Lisbon, Portugal", and the Kyoto photos
  "Tokyo". Places showed 74 "Lisbon" photos, 12 of them from Spain.
- **Fix**: set a distance cutoff (about 50 km). Beyond it, store the
  country only when it is known, or nothing, and add "approximate place"
  to the result. The Places page suggests the world dataset once any photo
  goes past the cutoff (after B4 is fixed).

### Cosmetic

- **C1.** The Settings folders card says "Add a folder in Settings to
  start indexing" while the user is already in Settings.
- **C2.** In Spanish, the Shared-models reasons stay in English ("Faustus
  not reachable on configured/default ports..."). "Guardar ajustes del
  backend compartido" is jargon. The legacy "Ollama vision model" card
  repeats the Shared models card and confuses which one wins.
- **C3.** Country names stay in English in the Spanish UI ("Spain",
  "Japan"): they come from `country_names.tsv`.
- **C4.** The Timeline's "On this day" thumbnails have no year. Month tiles
  in one row have uneven heights.
- **C5.** The 12 burst frames fill the first two search rows. A "collapse
  bursts" toggle (near duplicates within seconds) would help. Low priority.
- **C6.** Assistant activity does not show whether a result carried an
  image. It would have made the live HTTP 500 diagnosable from inside
  Argus.
- **C7.** Near-duplicate groups wider than the card are cut off at the
  right edge, with no visible scroll affordance.

## Relevance band calibration

Measured with `data-uxtest/calib.py` (scratch, not committed): 19 queries
against the 262 synthetic photos, each result marked by the data manifest.
The figures are cosine scores among each query's top 50 (copies left
out).

| Query class | CLIP ViT-B/32 | Colour fallback |
| --- | --- | --- |
| Relevant hits (10th / 50th / 90th percentile) | 0.232 / 0.282 / 0.311 | 0.001 / 0.087 / 0.185 |
| Irrelevant hits (50th / 90th / 99th percentile) | 0.222 / 0.250 / 0.288 | 0.237 / 0.292 / 0.340 |
| Best score for concepts absent from the library ("a red car", "a baby", "fireworks") | 0.235-0.253 | 0.278-0.287 |
| Colour queries ("orange sunset", "green screen") | normal CLIP behaviour | relevant 0.05-0.15 vs irrelevant ~0.004 for orange; ~0.001 for everything with green |

Starting point for B2/B3:

- **CLIP**: `strong` at 0.27 or more, `medium` from 0.245 to 0.27, `weak`
  below 0.245. Also demote a result to `weak` when it is more than 0.04
  below the query's best score. When the best result is not `strong`, add
  "no strong match" to the note. Absent concepts then land in `medium` at
  best, and the model is told so.
- **Fallback**: with no colour word, every result is `weak` and the order
  is called arbitrary. With a colour word, `medium` when the score is at
  least half the best score and the best score is 0.02 or more, otherwise
  `weak`. Never `strong`.
- Synthetic drawings are not real photos. Re-check the CLIP thresholds with
  `pytest -m model` on the demo scenes and, when possible, a few real
  photos. docs/MCP.md already describes a good CLIP match as roughly
  0.2-0.35, which agrees with the table.

## Agent walkthrough numbers

| Instance | Calls | Text tokens (approx.) | Images received | Failed checks |
| --- | --- | --- | --- | --- |
| Colour fallback | 26 | 35.2k | 10 (8 not asked for) | 16 |
| CLIP | 26 | 34.4k | 10 (8 not asked for) | 12 |

The tool list costs about 2.8k tokens for 9 tools. `photos_search` alone
takes about 750 of them: its docstring lists every field and filter.
Trimming it to what a model needs to choose (the filters, the bands, "ask
for the contact sheet only if you can see images") is part of B1/B2. The
checks that failed on both instances map to B1, B2, B5, A2, A7 and A9. Of
the four that failed only on the fallback, two are B3 (the dog and
clapperboard picks). One is B5: the CLIP run's album check "passed" only
because the fallback run had already added the other photos. The last was
a Windows-only path in the script, replaced by a missing Linux folder
before the CLIP run.

## Not tested

- Windows specifics: "Open in Explorer" (hidden on Linux), `start.ps1` /
  `stop.ps1`, Windows paths with drive letters in the UI.
- A real Faustus with a text-only 27B model. B1 reproduces the
  live failure at the MCP level; the llama.cpp turn itself was not re-run
  here.
- Captions and query translation: no vision or language model server was
  running. Only the "Not available" states and `caption_error` were
  checked.
- Real photos: every image was synthetic. The CLIP thresholds and the
  near-duplicate false-positive rate need a check on real photos.
- Large libraries (20k+ photos), download speeds a home connection would
  see, and HEIC files from real phones.
- Scheherazade's side of UC6 and Faustus's file-copy side of UC5 (outside
  this app).

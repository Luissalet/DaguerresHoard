# Use cases

Eight concrete scenarios Argus's Hoard has to serve. They are the script
for the usability walkthroughs (`docs/USABILITY_REPORT.md`): each one was
walked in the browser (Playwright, screenshots read by a person) and the
agent ones over real MCP stdio (`scripts/agent_walkthrough.py`).

**The persona behind all of them**: a developer on a Windows PC who uses
Faustus every day with a text-only 27B model on llama.cpp, keeps about a
decade of phone and camera photos in `Pictures`, sometimes shoots short
films with friends, and switches the UI between Spanish and English. Has
no patience for a tool that looks busy but gives wrong answers with
confidence.

Test data for all of them: `python scripts/make_uxtest_photos.py` builds a
synthetic but realistically messy `Pictures` folder in `data-uxtest/`
(camera roll by year/month, a Lisbon trip, a Tokyo/Kyoto trip, a beach day
with a 12-frame burst, a short-film shoot, WhatsApp copies without EXIF, a
byte-identical phone backup, screenshots, TIFF scans, HEIC/WebP/GIF, a
truncated JPEG, an empty file, junk files). No real photos, no personal
data.

---

## UC1 - First run: "point it at my Pictures folder and make search actually work"

- **Who**: the owner, on a fresh install, in the UI.
- **Goal**: go from nothing to a library where a content search ("sunset
  over the sea") returns real matches.
- **Start**: app just started with an empty data folder; no folders
  registered; CLIP model not downloaded.
- **Steps (UI)**:
  1. Open `http://127.0.0.1:8814`. Read what the first screen asks for.
  2. Add the `Pictures` folder (Settings -> Folders, or whatever the
     empty state offers).
  3. Watch the scan: progress, files/s, ETA; what happens to the empty,
     truncated and junk files.
  4. Understand that search is colour-only until the model is downloaded;
     download it (about 600 MB); watch the re-embedding.
  5. Search "sunset over the sea".
- **Done when**: every readable photo is indexed, unreadable files are
  reported (not silently dropped, not blocking), the model is active, and
  the search returns sunsets first. The owner never had to guess the next
  step.

## UC2 - "Do you still have the photo of the dog on the beach from last summer?"

- **Who**: the owner in the UI, then the same question to Faustus.
- **Goal**: find one specific photo by content and approximate date.
- **Start**: UC1 done (model active). The dog appears in a 12-frame burst
  and in two other shots from a July 2024 beach day near Lisbon.
- **Steps (UI)**: Search -> type `perro en la playa` (Spanish on purpose)
  -> narrow to 2024 / summer -> open the lightbox -> "similar" strip ->
  "Open folder".
- **Steps (agent)**: *"Faustus, ¿tienes la foto del perro en la playa del
  verano pasado?"* The model should call `photos_search(query="dog on the
  beach", taken_after="2024-06-01", taken_before="2024-09-30")`, read the
  compact results, and - being text-only - never receive an image it did
  not ask for. It answers with the date, place and path of the best hits
  and says honestly how sure the ranking is.
- **Done when**: the burst and the two other dog photos are at the top;
  the agent's answer names real paths and does not invent a count ("I
  found 87 photos") or a content claim it could not see.

## UC3 - Free up space: bursts, WhatsApp copies and the old phone backup

- **Who**: the owner in the UI; later "Faustus, ¿cuánto espacio ocupan las
  fotos repetidas?".
- **Goal**: know which files are extra copies, which one to keep, and how
  much space deleting the rest would free - then delete them in Explorer.
- **Start**: library indexed. `Copia movil 2024` holds 15 byte-identical
  copies; `WhatsApp Images` holds 18 downscaled copies without EXIF; the
  burst has 12 near-identical frames.
- **Steps (UI)**: Duplicates -> exact -> check keeper -> "Copy paths" ->
  Near duplicates -> the burst group and the WhatsApp copies.
- **Steps (agent)**: `photos_duplicates(kind="exact")`, then
  `kind="near"`; answer with `reclaimable_bytes_total` and the keepers.
- **Done when**: the owner has a list of paths to delete and the keeper
  of each group is the full-resolution original, not the WhatsApp copy;
  the agent never claims it deleted anything.

## UC4 - "Faustus, make an album with the Lisbon trip" (agent-driven)

- **Who**: Faustus with the text-only 27B model.
- **Goal**: an album "Lisboa 2024" with every photo of the July 2024 trip.
- **Start**: library indexed; the trip is 54 photos (40 + burst + 2).
- **Prompt**: *"Faustus, haz un álbum 'Lisboa 2024' con todas las fotos
  del viaje a Lisboa de julio de 2024."*
- **Expected calls**: `photos_library` (is it indexed?) ->
  `photos_search(query="photo", place="Lisbon", year=2024, month=7,
  limit=50)` -> more pages if `has_more` -> `photos_album(name="Lisboa
  2024", photo_ids=[...])`.
- **Done when**: the album holds every trip photo (not just the first
  50), and the model can tell from the results alone that it has them all.

## UC5 - A vertical portrait for a CV, copied to the CV folder (combined with Faustus's own file tools)

- **Who**: Faustus, combining Argus with its own file tools.
- **Goal**: find a good-resolution vertical portrait and copy it to
  `Documents\CV\` for a CV.
- **Prompt**: *"Faustus, busca una foto de retrato vertical con buena
  resolución para el CV y cópiala a mi carpeta del CV."*
- **Expected calls**: `photos_search(query="portrait photo of a person",
  orientation="portrait", min_megapixels=2)` -> `photos_describe(photo_id)`
  for the path and resolution -> Faustus's own file-copy tool with that
  path. Argus itself never copies or moves anything.
- **Done when**: the chosen photo really is a portrait (vertical, a
  person), the path is absolute and usable by another tool, and a
  text-only model had enough information (score band, size, orientation)
  to pick without seeing the image.

## UC6 - Short-film behind-the-scenes post (combined with Scheherazade's Hoard)

- **Who**: the owner in the UI, then Faustus.
- **Goal**: pick the clapperboard and green-screen shots from the March
  2025 shoot of "La Estación" for a behind-the-scenes post, and
  collect them in an album; the story bible for the same project lives in
  Scheherazade's Hoard.
- **Steps (UI)**: Search "clapperboard" -> lightbox -> similar strip ->
  add to album "Rodaje La Estación".
- **Prompt**: *"Faustus, busca las fotos de la claqueta y del croma del
  rodaje de marzo y mételas en el álbum 'Rodaje La Estación'; luego apunta en
  la ficha de la historia en Scheherazade cuántas tomas tenemos."*
- **Expected calls**: `photos_search(query="film clapperboard",
  taken_after="2025-03-01", taken_before="2025-03-31")`,
  `photos_search(query="green screen studio", ...)` ->
  `photos_album(...)` -> Scheherazade's own tools for the note.
- **Done when**: the album holds clapperboard and green-screen shots from
  that shoot and nothing from the Tokyo trip that happens to share colours.

## UC7 - "Faustus, what did I do on this day?" (agent-driven)

- **Who**: Faustus on 22 September.
- **Goal**: a short "on this day" memory with dates and places.
- **Prompt**: *"Faustus, ¿qué fotos hice un día como hoy en otros años?"*
- **Expected calls**: `photos_timeline()` -> `on_this_day` ids ->
  `photos_describe(photo_id)` for the place/camera of each.
- **Done when**: the answer lists the right years with places, without
  images the model did not ask for.

## UC8 - Where have I been? Places and timeline, and the receipts from the trip

- **Who**: the owner in the UI.
- **Goal**: browse places and months; then find the café receipts from the
  Lisbon trip for an expense note.
- **Steps (UI)**: Places -> Lisbon, Tokyo, and the Cádiz beach day (GPS far
  from every bundled city) -> Timeline 2024 -> July -> Search "paper
  receipt" with the July 2024 filter.
- **Done when**: places are right (or honestly approximate), the Cádiz
  photos are not labelled with the wrong country, and the receipts come
  first in the search.

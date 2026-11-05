export type Lang = "en" | "es";

export interface Dict {
  compare_title: string;
  compare_scope: string;
  compare_photo: string;
  compare_choose: string;
  compare_not_visible: string;
  compare_swap: string;
  compare_open: string;
  compare_preview: string;
  compare_retry: string;
  compare_dimensions: string;
  compare_size: string;
  compare_camera: string;
  compare_exposure: string;
  compare_not_recorded: string;
  match_title: string;
  match_reference: string;
  match_choose: string;
  match_use_this: string;
  match_strength: string;
  match_batch: string;
  match_note: string;
  match_create: string;
  match_result: string;
  match_parameters: string;
  match_omitted: string;
  appName: string;
  nav_library: string;
  nav_search: string;
  nav_duplicates: string;
  nav_timeline: string;
  nav_places: string;
  nav_albums: string;
  nav_settings: string;
  nav_activity: string;
  nav_videos: string;
  videos_empty_title: string;
  videos_empty_body: string;
  video_key_frames: string;
  video_play_from: (ts: string) => string;
  video_hide_player: string;
  video_frames_n: (n: number) => string;
  video_no_frames: string;
  video_player_failed: string;
  clip_title: string;
  clip_help: string;
  clip_start: string;
  clip_end: string;
  clip_use_position: string;
  clip_target: string;
  clip_interval_help: string;
  clip_busy: string;
  clip_export: string;
  clip_pending: string;
  clip_requested: string;
  clip_measured: string;
  clip_timing_note: string;
  clip_preview: string;
  clip_download: string;
  clip_receipt: string;
  clip_retry: string;
  search_placeholder: string;
  search_button: string;
  search_filter_help: string;
  filtered_listing_note: string;
  filtered_listing_limit: string;
  filtered_count: (returned: number, total: number) => string;
  filters: string;
  filter_year: string;
  filter_place: string;
  filter_folder: string;
  filter_camera: string;
  filter_orientation: string;
  orientation_any: string;
  orientation_landscape: string;
  orientation_portrait: string;
  empty_library_title: string;
  empty_library_body: string;
  empty_search_title: string;
  empty_search_body: string;
  no_results: string;
  loading: string;
  photos_count: (n: number) => string;
  ranked_count: (returned: number, total: number) => string;
  open_in_explorer: string;
  similar_photos: string;
  similar_source: string;
  similar_index: string;
  similar_progress: (shown: number, total: number) => string;
  similar_more: string;
  similar_retry: string;
  similar_empty: string;
  similar_band: Record<"strong" | "medium" | "weak", string>;
  close: string;
  exact_duplicates: string;
  near_duplicates: string;
  keeper: string;
  copy_paths: string;
  copied: string;
  on_this_day: string;
  year: string;
  month_names: string[];
  roots: string;
  add_folder: string;
  folder_path_placeholder: string;
  add: string;
  scan_now: string;
  scanning: string;
  remove: string;
  confirm_remove: string;
  yes_remove: string;
  cancel: string;
  model_status: string;
  geocoder_status: string;
  download_geonames: string;
  ollama_url: string;
  ollama_model: string;
  test_connection: string;
  connection_ok: string;
  connection_failed: string;
  save: string;
  saved: string;
  albums_empty: string;
  new_album: string;
  album_name_placeholder: string;
  create: string;
  assistant_activity_empty: string;
  tool: string;
  when: string;
  duration: string;
  result: string;
  ok: string;
  failed: string;
  select: string;
  selected: string;
  export_selection: string;
  export_title: string;
  export_note: string;
  export_choose: string;
  album_selection: string;
  album_selection_note: string;
  album_selection_empty: string;
  album_selection_review: (n: number) => string;
  album_selection_working: string;
  album_selection_created: string;
  album_selection_existing: string;
  album_selection_result: (added: number, total: number) => string;
  album_selection_unknown: string;
  export_first: string;
  export_clear: string;
  export_working: string;
  export_gallery: string;
  export_download: string;
  export_sheet: string;
  export_manifest: string;
  export_result: (returned: number, requested: number) => string;
  export_omitted: (n: number) => string;
  make_album_from_selection: string;
  places_empty: string;
  places_approximate_note: (n: number) => string;
  theme_light: string;
  theme_dark: string;
  lang_switch: string;
  caption: string;
  generate_caption: string;
  generating: string;
  photo_details: string;
  taken: string;
  camera: string;
  lens: string;
  exposure: string;
  path: string;
  library_count: (n: number) => string;
  indexing_now: string;
  fallback_title: string;
  fallback_body: string;
  open_settings: string;
  filter_from: string;
  filter_to: string;
  add_to_album: string;
  craft_tools: string;
  craft_photo_editable: string;
  craft_develop: string;
  craft_exposure: string;
  craft_working: string;
  craft_unavailable: string;
  craft_open_project: string;
  craft_open_editor: string;
  craft_view_export: string;
  craft_original_safe: string;
  craft_failed: string;
  album_input_placeholder: string;
  added_to: (name: string) => string;
  dup_summary: (groups: number, bytes: string) => string;
  dup_group_reclaim: (bytes: string) => string;
  dup_summary_near: (groups: number, bytes: string) => string;
  dup_group_reclaim_near: (bytes: string) => string;
  open_folder: string;
  back_to_timeline: string;
  model_active: string;
  model_semantic: string;
  model_fallback: string;
  model_download: string;
  model_downloading: string;
  model_note: string;
  model_downloaded: (size: string) => string;
  stale_photos: (n: number) => string;
  excluded_globs: string;
  excluded_placeholder: string;
  edit: string;
  captions_batch: string;
  captions_note: string;
  geocoder_note: string;
  geocoder_bundled: string;
  geocoder_full: string;
  delete_album: string;
  confirm_delete_album: string;
  yes_delete: string;
  select_photos: string;
  remove_selected: (n: number) => string;
  confirm_remove_from_album: (n: number) => string;
  heic_missing: string;
  job_errors: (n: number) => string;
  file_date: string;
  missing_file: string;
  arguments: string;
  by_assistant: string;
  error_generic: string;
  job_started: string;
  folder_unreachable: string;
  score: string;
  shared_models: string;
  shared_models_note: string;
  backend_row_vision: string;
  backend_row_llm: string;
  backend_recheck: string;
  backend_resolved: string;
  backend_unavailable: string;
  backend_faustus_url: string;
  backend_faustus_token: string;
  backend_token_set: string;
  backend_token_placeholder: string;
  backend_override_url: string;
  backend_override_model: string;
  backend_save_overrides: string;
  translate_search_label: string;
  searched_for: (english: string) => string;
  not_translated: string;
  note_translate_query: string;
  note_no_strong_match: string;
  note_filters_exclude_all: string;
  note_stale_photos: string;
  no_vision_model: string;
  no_llm_model: string;
  backend_forget_token: string;
  edits_title: string;
  edits_rating: string;
  edits_rejected: string;
  edits_reject: string;
  edits_unreject: string;
  edits_reject_help: string;
  edits_label: string;
  edits_keywords: string;
  edits_save: string;
  edits_saved: string;
  edits_recipe: string;
  edits_no_recipe: string;
  recipe_exposure: string;
  recipe_exposure_stored: string;
  recipe_exposure_absent: string;
  recipe_exposure_save: string;
  recipe_exposure_clear: string;
  recipe_exposure_help: string;
  recipe_wb_title: string;
  recipe_wb_temperature: string;
  recipe_wb_tint: string;
  recipe_wb_absent: string;
  recipe_wb_save: string;
  recipe_wb_clear_temperature: string;
  recipe_wb_clear_tint: string;
  recipe_wb_help: string;
  sidecar_title: string;
  sidecar_none: string;
  sidecar_by_daguerre: string;
  sidecar_by_foreign: string;
  sidecar_invalid: string;
  sidecar_changed: string;
  sidecar_shared_name: string;
  sidecar_reread: string;
  sidecar_write: string;
  sidecar_write_off: string;
  sidecar_written: string;
  imported_not_applied: (n: number) => string;
  settings_xmp_label: string;
  settings_xmp_hint: string;
}

export const dict: Record<Lang, Dict> = {
  en: {
    compare_title: "Compare photos",
    compare_scope: "Compare photos from the currently loaded list. Previews and saved metadata are shown without choosing a better photo or changing your files.",
    compare_photo: "Photo",
    compare_choose: "Choose a photo",
    compare_not_visible: "This selection is no longer in the visible list. Choose another photo.",
    compare_swap: "Swap A/B",
    compare_open: "Open photo",
    compare_preview: "Existing preview; not a full-resolution or 1:1 view.",
    compare_retry: "Retry this photo",
    compare_dimensions: "Dimensions",
    compare_size: "File size",
    compare_camera: "Camera / lens",
    compare_exposure: "Exposure",
    compare_not_recorded: "Not recorded",
    appName: "Daguerre's Hoard",
    nav_library: "Library",
    nav_search: "Search",
    nav_duplicates: "Duplicates",
    nav_timeline: "Timeline",
    nav_places: "Places",
    nav_albums: "Albums",
    nav_settings: "Settings",
    nav_activity: "Assistant activity",
    nav_videos: "Videos",
    videos_empty_title: "No videos yet",
    videos_empty_body: "Videos in your folders show up here with their key frames after the next scan.",
    video_key_frames: "Key frames",
    video_play_from: (ts: string) => `Play from ${ts}`,
    video_hide_player: "Hide player",
    video_frames_n: (n: number) => `${n} key frame${n === 1 ? "" : "s"}`,
    video_no_frames: "No key frames (ffmpeg not found, or the video could not be read)",
    video_player_failed: "This browser cannot play the video; the key frames still work.",
    clip_title: "Export an interval",
    clip_help: "Create a separate, re-encoded MP4. The original stays unchanged. Enter seconds or use the ready player's position.",
    clip_start: "Start (seconds)",
    clip_end: "End (seconds)",
    clip_use_position: "Use player position",
    clip_target: "Requested duration",
    clip_interval_help: "Choose a start at or after zero and an end after it, within the video.",
    clip_busy: "Exporting…",
    clip_export: "Export interval",
    clip_pending: "You can keep editing. Closing this view does not cancel an export already started.",
    clip_requested: "Exported request",
    clip_measured: "Measured output duration",
    clip_timing_note: "H.264 MP4; first audio track as AAC if present. Frames and the container can adjust the duration.",
    clip_preview: "Exported interval",
    clip_download: "Download MP4",
    clip_receipt: "Download receipt",
    clip_retry: "Retry export",
    search_placeholder: "Describe what you are looking for…",
    search_button: "Search",
    search_filter_help: "Describe a photo or leave the description blank and use the filters. Filters are combined.",
    filtered_listing_note: "Photos matching the submitted filters, newest first. No similarity ranking.",
    filtered_listing_limit: "Up to 50 photos are shown; refine the filters to narrow this list.",
    filtered_count: (returned, total) => `${returned} shown of ${total} photo${total === 1 ? "" : "s"}`,
    filters: "Filters",
    filter_year: "Year",
    filter_place: "Place",
    filter_folder: "Folder",
    filter_camera: "Camera",
    filter_orientation: "Orientation",
    orientation_any: "Any",
    orientation_landscape: "Landscape",
    orientation_portrait: "Portrait",
    empty_library_title: "No photos indexed yet",
    empty_library_body: "Add a folder in Settings to start indexing your photos.",
    empty_search_title: "Search your photos",
    empty_search_body: "Use the filters without a description, or describe a photo such as “sunset on the beach”. English works best for content search.",
    no_results: "No photos matched your search.",
    loading: "Loading…",
    photos_count: (n: number) => `${n} photo${n === 1 ? "" : "s"}`,
    // B2 (live report): "50 photos / 262" read as "262 matches". Results
    // are ranked by similarity, not filtered -- this says so.
    ranked_count: (returned, total) => `the best ${returned} of ${total} photo${total === 1 ? "" : "s"}, ranked`,
    open_in_explorer: "Open in Explorer",
    similar_photos: "Similar photos",
    similar_source: "Source photo",
    similar_index: "Current index",
    similar_progress: (shown, total) => `${shown} shown of ${total} indexed · ordered by similarity`,
    similar_more: "Load more similar photos",
    similar_retry: "Retry this page",
    similar_empty: "No other photos are indexed for the current model.",
    similar_band: { strong: "Strong similarity", medium: "Medium similarity", weak: "Weak similarity" },
    close: "Close",
    exact_duplicates: "Exact duplicates",
    near_duplicates: "Near duplicates",
    keeper: "Keeper",
    copy_paths: "Copy paths of the extra copies",
    copied: "Copied",
    on_this_day: "On this day",
    year: "Year",
    month_names: [
      "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ],
    roots: "Indexed folders",
    add_folder: "Add folder",
    folder_path_placeholder: "Absolute folder path, e.g. C:\\Users\\you\\Pictures",
    add: "Add",
    scan_now: "Scan now",
    scanning: "Scanning…",
    remove: "Remove",
    confirm_remove: "Remove this folder from the index? Files are not touched.",
    yes_remove: "Yes, remove",
    cancel: "Cancel",
    model_status: "Image model",
    geocoder_status: "Places data",
    download_geonames: "Download full world cities dataset",
    ollama_url: "Ollama URL",
    ollama_model: "Ollama vision model",
    test_connection: "Test connection",
    connection_ok: "Connected",
    connection_failed: "Connection failed",
    save: "Save",
    saved: "Saved",
    albums_empty: "No albums yet. Open a photo and use “Add to album”, or ask the assistant to make one.",
    new_album: "New album",
    album_name_placeholder: "Album name",
    create: "Create",
    assistant_activity_empty: "The assistant has not called any tool yet.",
    tool: "Tool",
    when: "When",
    duration: "Duration",
    result: "Result",
    ok: "OK",
    failed: "Failed",
    select: "Select",
    selected: "selected",
    export_selection: "Export selection",
    export_title: "Gallery title",
    export_note: "Create a standalone HTML gallery, JPEG contact sheet and JSON manifest from up to 20 photos. Previews are up to 512 px; originals are not included or changed.",
    export_choose: "Choose photos in the order you want them to appear.",
    album_selection: "Add selection to album",
    album_selection_note: "Choose loaded photos below and enter a new or existing album name. Photos are referenced, never copied or moved. Matching names ignore case and accents.",
    album_selection_empty: "Select photos in the grid to add them together.",
    album_selection_review: (n) => `Review selected photos (${n})`,
    album_selection_working: "Adding…",
    album_selection_created: "Album created",
    album_selection_existing: "Existing album",
    album_selection_result: (added, total) => `${added} newly added · ${total} in the album`,
    album_selection_unknown: "Unknown photo IDs",
    export_first: "Select first 20 loaded",
    export_clear: "Clear selection",
    export_working: "Creating gallery…",
    export_gallery: "Open gallery",
    export_download: "Download HTML",
    export_sheet: "Download contact sheet",
    export_manifest: "Download manifest",
    export_result: (returned, requested) => `${returned} of ${requested} photos exported`,
    export_omitted: (n) => `${n} photos could not be included. See the manifest for details.`,
    make_album_from_selection: "Add to album",
    places_empty: "No photos with GPS data yet.",
    places_approximate_note: (n) =>
      `${n} photo${n === 1 ? "" : "s"} ${n === 1 ? "is" : "are"} too far from the built-in 10 cities to place precisely. Download the full world dataset in Settings for accurate places.`,
    theme_light: "Light",
    theme_dark: "Dark",
    lang_switch: "ES",
    caption: "Caption",
    generate_caption: "Generate caption",
    generating: "Generating…",
    photo_details: "Photo details",
    taken: "Taken",
    camera: "Camera",
    lens: "Lens",
    exposure: "Exposure",
    path: "Path",
    library_count: (n: number) => `${n.toLocaleString("en")} photo${n === 1 ? "" : "s"}`,
    indexing_now: "Indexing…",
    fallback_title: "Content search is not available yet",
    fallback_body:
      "Daguerre is using its colour-only fallback, so searches only understand colours. Download the image model in Settings to search by what is in your photos.",
    open_settings: "Open Settings",
    filter_from: "From",
    filter_to: "To",
    add_to_album: "Add to album",
    match_title: "Match a photo series",
    match_reference: "Reference photo",
    match_choose: "Choose from these photos",
    match_use_this: "Use this photo as reference",
    match_strength: "Strength",
    match_batch: "Match these photos (up to 20)",
    match_note: "Global exposure and colour for comparable scenes. Creates PNG copies from original pixels; saved retouch recipes stay separate.",
    match_create: "Create matched copies",
    match_result: "Matched copy",
    match_parameters: "Saved matching parameters",
    match_omitted: "Photos omitted",
    craft_tools: "Daguerre image editors",
    craft_photo_editable: "Create layered copy",
    craft_develop: "Develop copy",
    craft_exposure: "Exposure",
    craft_working: "Working…",
    craft_unavailable: "The image engine is unavailable.",
    craft_open_project: "Download editable project",
    craft_open_editor: "Open full editor",
    craft_view_export: "View exported image",
    craft_original_safe: "The indexed original stays untouched. The result is saved under Daguerre data.",
    craft_failed: "Craft operation failed",
    album_input_placeholder: "New or existing album",
    added_to: (name: string) => `Added to “${name}”`,
    dup_summary: (groups: number, bytes: string) =>
      `${groups} group${groups === 1 ? "" : "s"} · ${bytes} would be freed by keeping one copy of each`,
    dup_group_reclaim: (bytes: string) => `${bytes} in extra copies`,
    dup_summary_near: (groups: number, bytes: string) =>
      `${groups} group${groups === 1 ? "" : "s"} of look-alike photos · up to ${bytes} · they can be different photos, check each group before deleting`,
    dup_group_reclaim_near: (bytes: string) => `up to ${bytes} if the others really are copies`,
    open_folder: "Open folder",
    back_to_timeline: "Timeline",
    model_active: "Active model",
    model_semantic: "CLIP ViT-B/32: searches by content",
    model_fallback: "Colour-only fallback: the image model is not downloaded",
    model_download: "Download image model (about 600 MB)",
    model_downloading: "Downloading and re-indexing…",
    model_note: "Downloaded once from Hugging Face into the data folder; afterwards everything runs offline.",
    model_downloaded: (size: string) => `Downloaded (${size} on disk)`,
    stale_photos: (n: number) => `${n} photo${n === 1 ? "" : "s"} still to be analysed with this model (run a scan).`,
    excluded_globs: "Excluded patterns",
    excluded_placeholder: "e.g. */Screenshots/*, *.gif",
    edit: "Edit",
    captions_batch: "Caption photos that have none",
    captions_note: "Sends each photo to your local Ollama model; it can take a while and runs in the background.",
    geocoder_note: "Downloads about 10 MB from GeoNames (CC BY 4.0) and relabels every photo with GPS.",
    geocoder_bundled: "Built-in list of 10 cities",
    geocoder_full: "GeoNames cities1000 (worldwide)",
    delete_album: "Delete album",
    confirm_delete_album: "Delete this album? The photos stay where they are.",
    yes_delete: "Yes, delete",
    select_photos: "Select photos",
    remove_selected: (n) => `Remove ${n} photo${n === 1 ? "" : "s"}`,
    confirm_remove_from_album: (n) =>
      `Remove ${n} photo${n === 1 ? "" : "s"} from this album? ${n === 1 ? "The file stays where it is" : "The files stay where they are"}.`,
    heic_missing: "HEIC support is not installed, so .heic files are skipped.",
    job_errors: (n: number) => `${n} file${n === 1 ? "" : "s"} could not be read`,
    file_date: "file date, no EXIF",
    missing_file: "The original file is not reachable right now.",
    arguments: "Arguments",
    by_assistant: "by the assistant",
    error_generic: "Something went wrong",
    job_started: "Started in the background",
    folder_unreachable: "Folder not reachable",
    score: "Match",
    shared_models: "Shared models",
    shared_models_note:
      "Text and vision use the global model selected in Faustus. If it is unavailable, the operation reports an error. Legacy local URLs and model names remain saved below for continuity; they do not select an alternative model.",
    backend_row_vision: "Vision (captions)",
    backend_row_llm: "Language model (query translation)",
    backend_recheck: "Re-check",
    backend_resolved: "Available",
    backend_unavailable: "Not available",
    backend_faustus_url: "Faustus URL",
    backend_faustus_token: "Faustus token",
    backend_token_set: "Token saved",
    backend_token_placeholder: "Leave blank to keep the saved token",
    backend_override_url: "Saved legacy URL",
    backend_override_model: "Saved legacy model",
    backend_save_overrides: "Save shared-backend settings",
    translate_search_label: "Translate non-English searches to English automatically",
    searched_for: (english: string) => `Searched for: “${english}”`,
    not_translated: "Not translated: no language model is available (see Settings → Shared models).",
    note_translate_query: "The image model understands English best: try writing the search in English.",
    note_no_strong_match: "No strong match: even the best results are only a partial match.",
    note_filters_exclude_all: "No photo passes these filters.",
    note_stale_photos: "Some photos are still being analysed and are not in these results yet.",
    no_vision_model: "No vision model is loaded. Faustus can serve one, or load one in Ollama.",
    no_llm_model: "No language model is loaded. Faustus can serve one, or load one in Ollama.",
    backend_forget_token: "Forget token",
    edits_title: "Rating and retouch",
    edits_rating: "Rating",
    edits_rejected: "Rejected",
    edits_reject: "Mark as rejected",
    edits_unreject: "Clear rejection",
    edits_reject_help: "This rating mark does not delete or move the photo. Clearing it leaves the photo unrated.",
    edits_label: "Label (for example Red)",
    edits_keywords: "Keywords, separated by commas",
    edits_save: "Save",
    edits_saved: "Saved in Daguerre.",
    edits_recipe: "Develop recipe",
    edits_no_recipe: "No develop settings.",
    recipe_exposure: "Stored recipe exposure (EV)",
    recipe_wb_title: "Recipe white balance",
    recipe_wb_temperature: "Recipe temperature (K)",
    recipe_wb_tint: "Recipe tint",
    recipe_wb_absent: "No adjustment",
    recipe_wb_save: "Save white balance changes",
    recipe_wb_clear_temperature: "Clear temperature only",
    recipe_wb_clear_tint: "Clear tint only",
    recipe_wb_help: "Temperature 2000–50000 K; tint −150 to +150, whole numbers. Empty is not zero: use Clear to remove a saved setting. Saves recipe settings for compatible developers; Daguerre does not render them in the preview. These are not measured Kelvin values for JPEG/TIFF. XMP writing follows the current setting below.",
    recipe_exposure_stored: "Saved value",
    recipe_exposure_absent: "No exposure adjustment",
    recipe_exposure_save: "Save exposure",
    recipe_exposure_clear: "Clear exposure only",
    recipe_exposure_help: "−5 to +5 EV, two decimals. Saves this recipe setting without rendering or changing the original. Other settings remain. The separate export slider has a −3 to +3 EV range.",
    sidecar_title: ".xmp sidecar",
    sidecar_none: "none next to this photo.",
    sidecar_by_daguerre: "written by Daguerre.",
    sidecar_by_foreign: "made by another program; Daguerre read it and keeps it intact.",
    sidecar_invalid: "not valid XMP; Daguerre will not touch it.",
    sidecar_changed: "Changed on disk since it was read.",
    sidecar_shared_name: "Another file in this folder has the same name, so the sidecar is called <photo name>.<extension>.xmp.",
    sidecar_reread: "Re-read",
    sidecar_write: "Write .xmp",
    sidecar_write_off: "Turn on \"Write .xmp sidecars\" in Settings to write it.",
    sidecar_written: "Saved, and the .xmp sidecar is up to date.",
    imported_not_applied: (n: number) => `${n} imported settings that Daguerre does not apply`,
    settings_xmp_label: "Write .xmp sidecars next to edited photos (off by default)",
    settings_xmp_hint:
      "Ratings, labels, keywords and develop recipes are kept in Daguerre. With this on they are also saved as standard .xmp files next to each photo, for RAW developers. The photo itself is never changed, and an existing .xmp is backed up and merged, not replaced.",
  },
  es: {
    compare_title: "Comparar fotos",
    compare_scope: "Compara fotos de la lista cargada en esta vista. Muestra vistas previas y metadatos guardados, sin elegir una foto mejor ni cambiar tus archivos.",
    compare_photo: "Foto",
    compare_choose: "Elige una foto",
    compare_not_visible: "Esta selección ya no está en la lista visible. Elige otra foto.",
    compare_swap: "Intercambiar A/B",
    compare_open: "Abrir foto",
    compare_preview: "Vista previa existente; no es una vista a resolución original ni 1:1.",
    compare_retry: "Reintentar esta foto",
    compare_dimensions: "Dimensiones",
    compare_size: "Tamaño",
    compare_camera: "Cámara / objetivo",
    compare_exposure: "Exposición",
    compare_not_recorded: "Sin dato guardado",
    appName: "Daguerre's Hoard",
    nav_library: "Biblioteca",
    nav_search: "Buscar",
    nav_duplicates: "Duplicados",
    nav_timeline: "Cronología",
    nav_places: "Lugares",
    nav_albums: "Álbumes",
    nav_settings: "Ajustes",
    nav_activity: "Actividad del asistente",
    nav_videos: "Vídeos",
    videos_empty_title: "Aún no hay vídeos",
    videos_empty_body: "Los vídeos de tus carpetas aparecen aquí con sus fotogramas clave tras el siguiente escaneo.",
    video_key_frames: "Fotogramas clave",
    video_play_from: (ts: string) => `Reproducir desde ${ts}`,
    video_hide_player: "Ocultar reproductor",
    video_frames_n: (n: number) => `${n} fotograma${n === 1 ? "" : "s"} clave`,
    video_no_frames: "Sin fotogramas clave (no se encontró ffmpeg o no se pudo leer el vídeo)",
    video_player_failed: "Este navegador no puede reproducir el vídeo; los fotogramas clave siguen funcionando.",
    clip_title: "Exportar un intervalo",
    clip_help: "Crea un MP4 recodificado independiente. El original queda intacto. Escribe segundos o usa la posición del reproductor cuando esté listo.",
    clip_start: "Inicio (segundos)",
    clip_end: "Final (segundos)",
    clip_use_position: "Usar posición del reproductor",
    clip_target: "Duración solicitada",
    clip_interval_help: "Elige un inicio desde cero y un final posterior, dentro del vídeo.",
    clip_busy: "Exportando…",
    clip_export: "Exportar intervalo",
    clip_pending: "Puedes seguir editando. Cerrar esta vista no cancela una exportación ya iniciada.",
    clip_requested: "Petición exportada",
    clip_measured: "Duración de salida medida",
    clip_timing_note: "MP4 H.264; primera pista de audio como AAC si existe. Los fotogramas y el contenedor pueden ajustar la duración.",
    clip_preview: "Intervalo exportado",
    clip_download: "Descargar MP4",
    clip_receipt: "Descargar recibo",
    clip_retry: "Reintentar exportación",
    search_placeholder: "Describe lo que buscas…",
    search_button: "Buscar",
    search_filter_help: "Describe una foto o deja la descripción vacía y utiliza los filtros. Los filtros se combinan.",
    filtered_listing_note: "Fotos que cumplen los filtros enviados, de más reciente a más antigua. Sin clasificación por similitud.",
    filtered_listing_limit: "Se muestran hasta 50 fotos; ajusta los filtros para reducir el listado.",
    filtered_count: (returned, total) => `${returned} mostrada${returned === 1 ? "" : "s"} de ${total} foto${total === 1 ? "" : "s"}`,
    filters: "Filtros",
    filter_year: "Año",
    filter_place: "Lugar",
    filter_folder: "Carpeta",
    filter_camera: "Cámara",
    filter_orientation: "Orientación",
    orientation_any: "Cualquiera",
    orientation_landscape: "Horizontal",
    orientation_portrait: "Vertical",
    empty_library_title: "Aún no hay fotos indexadas",
    empty_library_body: "Añade una carpeta en Ajustes para empezar a indexar tus fotos.",
    empty_search_title: "Busca en tus fotos",
    empty_search_body: "Utiliza los filtros sin descripción o describe una foto, por ejemplo «atardecer en la playa». En inglés funciona mejor la búsqueda por contenido.",
    no_results: "Ninguna foto coincide con tu búsqueda.",
    loading: "Cargando…",
    photos_count: (n: number) => `${n} foto${n === 1 ? "" : "s"}`,
    ranked_count: (returned, total) =>
      `las ${returned} mejores de ${total} foto${total === 1 ? "" : "s"}, por similitud`,
    open_in_explorer: "Abrir en el Explorador",
    similar_photos: "Fotos similares",
    similar_source: "Foto de origen",
    similar_index: "Índice actual",
    similar_progress: (shown, total) => `${shown} mostradas de ${total} indexadas · ordenadas por parecido`,
    similar_more: "Cargar más fotos similares",
    similar_retry: "Reintentar esta página",
    similar_empty: "No hay otras fotos indexadas para el modelo actual.",
    similar_band: { strong: "Parecido alto", medium: "Parecido medio", weak: "Parecido bajo" },
    close: "Cerrar",
    exact_duplicates: "Duplicados exactos",
    near_duplicates: "Duplicados aproximados",
    keeper: "Conservar",
    copy_paths: "Copiar rutas de las copias extra",
    copied: "Copiado",
    on_this_day: "Un día como hoy",
    year: "Año",
    month_names: [
      "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
    ],
    roots: "Carpetas indexadas",
    add_folder: "Añadir carpeta",
    folder_path_placeholder: "Ruta absoluta, p. ej. C:\\Users\\tu\\Imágenes",
    add: "Añadir",
    scan_now: "Escanear ahora",
    scanning: "Escaneando…",
    remove: "Quitar",
    confirm_remove: "¿Quitar esta carpeta del índice? Los archivos no se tocan.",
    yes_remove: "Sí, quitar",
    cancel: "Cancelar",
    model_status: "Modelo de imagen",
    geocoder_status: "Datos de lugares",
    download_geonames: "Descargar base de datos mundial de ciudades",
    ollama_url: "URL de Ollama",
    ollama_model: "Modelo de visión de Ollama",
    test_connection: "Probar conexión",
    connection_ok: "Conectado",
    connection_failed: "Conexión fallida",
    save: "Guardar",
    saved: "Guardado",
    albums_empty: "Aún no hay álbumes. Abre una foto y usa «Añadir a álbum», o pídele al asistente que cree uno.",
    new_album: "Nuevo álbum",
    album_name_placeholder: "Nombre del álbum",
    create: "Crear",
    assistant_activity_empty: "El asistente todavía no ha usado ninguna herramienta.",
    tool: "Herramienta",
    when: "Cuándo",
    duration: "Duración",
    result: "Resultado",
    ok: "OK",
    failed: "Fallo",
    select: "Seleccionar",
    selected: "seleccionadas",
    export_selection: "Exportar selección",
    export_title: "Título de la galería",
    export_note: "Crea una galería HTML autónoma, una hoja de contactos JPEG y un manifiesto JSON de hasta 20 fotos. Son vistas previas de hasta 512 px; los originales no se incluyen ni se modifican.",
    export_choose: "Selecciona las fotos en el orden en que quieras que aparezcan.",
    album_selection: "Añadir selección a álbum",
    album_selection_note: "Selecciona fotos cargadas y escribe un nombre de álbum nuevo o existente. Las fotos se vinculan, nunca se copian ni mueven. Los nombres coinciden sin distinguir mayúsculas ni acentos.",
    album_selection_empty: "Selecciona fotos en la cuadrícula para añadirlas juntas.",
    album_selection_review: (n) => `Revisar fotos seleccionadas (${n})`,
    album_selection_working: "Añadiendo…",
    album_selection_created: "Álbum creado",
    album_selection_existing: "Álbum existente",
    album_selection_result: (added, total) => `${added} ${added === 1 ? "foto incorporada" : "fotos incorporadas"} ahora · ${total} en el álbum`,
    album_selection_unknown: "IDs de fotos desconocidos",
    export_first: "Seleccionar primeras 20 cargadas",
    export_clear: "Vaciar selección",
    export_working: "Creando galería…",
    export_gallery: "Abrir galería",
    export_download: "Descargar HTML",
    export_sheet: "Descargar hoja de contactos",
    export_manifest: "Descargar manifiesto",
    export_result: (returned, requested) => `${returned} de ${requested} fotos exportadas`,
    export_omitted: (n) => `No se han podido incluir ${n} fotos. Consulta el manifiesto para ver el detalle.`,
    make_album_from_selection: "Añadir a álbum",
    places_empty: "Aún no hay fotos con datos GPS.",
    places_approximate_note: (n) =>
      `${n} foto${n === 1 ? "" : "s"} ${n === 1 ? "está" : "están"} demasiado lejos de las 10 ciudades integradas para ubicarla${n === 1 ? "" : "s"} con precisión. Descarga el conjunto de datos mundial en Ajustes para ubicaciones exactas.`,
    theme_light: "Claro",
    theme_dark: "Oscuro",
    lang_switch: "EN",
    caption: "Descripción",
    generate_caption: "Generar descripción",
    generating: "Generando…",
    photo_details: "Detalles de la foto",
    taken: "Fecha",
    camera: "Cámara",
    lens: "Objetivo",
    exposure: "Exposición",
    path: "Ruta",
    library_count: (n: number) => `${n.toLocaleString("es")} foto${n === 1 ? "" : "s"}`,
    indexing_now: "Indexando…",
    fallback_title: "La búsqueda por contenido aún no está disponible",
    fallback_body:
      "Daguerre está usando su modo básico, que solo entiende colores. Descarga el modelo de imagen en Ajustes para buscar por lo que aparece en tus fotos.",
    open_settings: "Abrir Ajustes",
    filter_from: "Desde",
    filter_to: "Hasta",
    add_to_album: "Añadir a álbum",
    match_title: "Igualar una serie fotográfica",
    match_reference: "Foto de referencia",
    match_choose: "Elige entre estas fotos",
    match_use_this: "Usar esta foto como referencia",
    match_strength: "Intensidad",
    match_batch: "Igualar estas fotos (hasta 20)",
    match_note: "Exposición y color globales para escenas comparables. Crea copias PNG desde el original; las recetas de retoque guardadas permanecen aparte.",
    match_create: "Crear copias igualadas",
    match_result: "Copia igualada",
    match_parameters: "Parámetros de igualación guardados",
    match_omitted: "Fotos omitidas",
    craft_tools: "Editores de imagen de Daguerre",
    craft_photo_editable: "Crear copia por capas",
    craft_develop: "Revelar copia",
    craft_exposure: "Exposición",
    craft_working: "Procesando…",
    craft_unavailable: "El motor de imagen no está disponible.",
    craft_open_project: "Descargar proyecto editable",
    craft_open_editor: "Abrir editor completo",
    craft_view_export: "Ver imagen exportada",
    craft_original_safe: "El original indexado permanece intacto. El resultado se guarda en los datos de Daguerre.",
    craft_failed: "La operación Craft ha fallado",
    album_input_placeholder: "Álbum nuevo o existente",
    added_to: (name: string) => `Añadida a «${name}»`,
    dup_summary: (groups: number, bytes: string) =>
      `${groups} grupo${groups === 1 ? "" : "s"} · se liberarían ${bytes} conservando una copia de cada uno`,
    dup_group_reclaim: (bytes: string) => `${bytes} en copias de más`,
    dup_summary_near: (groups: number, bytes: string) =>
      `${groups} grupo${groups === 1 ? "" : "s"} de fotos parecidas · hasta ${bytes} · pueden ser fotos distintas, revisa cada grupo antes de borrar`,
    dup_group_reclaim_near: (bytes: string) => `hasta ${bytes} si las demás son de verdad copias`,
    open_folder: "Abrir carpeta",
    back_to_timeline: "Cronología",
    model_active: "Modelo activo",
    model_semantic: "CLIP ViT-B/32: busca por contenido",
    model_fallback: "Modo básico por colores: el modelo de imagen no está descargado",
    model_download: "Descargar el modelo de imagen (unos 600 MB)",
    model_downloading: "Descargando y reindexando…",
    model_note: "Se descarga una sola vez desde Hugging Face a la carpeta de datos; después todo funciona sin conexión.",
    model_downloaded: (size: string) => `Descargado (${size} en disco)`,
    stale_photos: (n: number) => `Quedan ${n} foto${n === 1 ? "" : "s"} por analizar con este modelo (lanza un escaneo).`,
    excluded_globs: "Patrones excluidos",
    excluded_placeholder: "p. ej. */Capturas/*, *.gif",
    edit: "Editar",
    captions_batch: "Describir las fotos que no tienen descripción",
    captions_note: "Envía cada foto a tu modelo local de Ollama; puede tardar y se ejecuta en segundo plano.",
    geocoder_note: "Descarga unos 10 MB de GeoNames (CC BY 4.0) y vuelve a etiquetar todas las fotos con GPS.",
    geocoder_bundled: "Lista integrada de 10 ciudades",
    geocoder_full: "GeoNames cities1000 (todo el mundo)",
    delete_album: "Eliminar álbum",
    confirm_delete_album: "¿Eliminar este álbum? Las fotos se quedan donde están.",
    yes_delete: "Sí, eliminar",
    select_photos: "Seleccionar fotos",
    remove_selected: (n) => `Quitar ${n} foto${n === 1 ? "" : "s"}`,
    confirm_remove_from_album: (n) =>
      `¿Quitar ${n} foto${n === 1 ? "" : "s"} de este álbum? El${n === 1 ? " archivo se queda" : "os archivos se quedan"} donde está${n === 1 ? "" : "n"}.`,
    heic_missing: "El soporte HEIC no está instalado, así que los archivos .heic se omiten.",
    job_errors: (n: number) => `${n} archivo${n === 1 ? "" : "s"} no se ${n === 1 ? "ha" : "han"} podido leer`,
    file_date: "fecha del archivo, sin EXIF",
    missing_file: "El archivo original no está accesible ahora mismo.",
    arguments: "Argumentos",
    by_assistant: "por el asistente",
    error_generic: "Algo ha fallado",
    job_started: "En marcha en segundo plano",
    folder_unreachable: "Carpeta no accesible",
    score: "Coincidencia",
    shared_models: "Modelos compartidos",
    shared_models_note:
      "Texto y visión utilizan el modelo global elegido en Faustus. Si no está disponible, la operación devuelve un error. Las URL y nombres de modelos locales anteriores se conservan debajo; no seleccionan un modelo alternativo.",
    backend_row_vision: "Visión (descripciones)",
    backend_row_llm: "Modelo de lenguaje (traducción de búsquedas)",
    backend_recheck: "Volver a comprobar",
    backend_resolved: "Disponible",
    backend_unavailable: "No disponible",
    backend_faustus_url: "URL de Faustus",
    backend_faustus_token: "Token de Faustus",
    backend_token_set: "Token guardado",
    backend_token_placeholder: "Déjalo en blanco para mantener el token guardado",
    backend_override_url: "URL anterior guardada",
    backend_override_model: "Modelo anterior guardado",
    backend_save_overrides: "Guardar ajustes del backend compartido",
    translate_search_label: "Traducir automáticamente las búsquedas que no estén en inglés",
    searched_for: (english: string) => `Buscado como: «${english}»`,
    not_translated: "Sin traducir: no hay ningún modelo de lenguaje disponible (mira Ajustes → Modelos compartidos).",
    note_translate_query: "El modelo de imagen entiende mejor el inglés: prueba a escribir la búsqueda en inglés.",
    note_no_strong_match: "Ninguna coincidencia clara: incluso los mejores resultados se parecen solo en parte.",
    note_filters_exclude_all: "Ninguna foto cumple estos filtros.",
    note_stale_photos: "Algunas fotos aún se están analizando y todavía no aparecen en estos resultados.",
    no_vision_model: "No hay ningún modelo de visión cargado. Faustus puede servir uno, o puedes cargarlo en Ollama.",
    no_llm_model: "No hay ningún modelo de lenguaje cargado. Faustus puede servir uno, o puedes cargarlo en Ollama.",
    backend_forget_token: "Olvidar el token",
    edits_title: "Valoración y retoque",
    edits_rating: "Valoración",
    edits_rejected: "Descartada",
    edits_reject: "Marcar como rechazada",
    edits_unreject: "Quitar rechazo",
    edits_reject_help: "Esta marca de valoración no borra ni mueve la foto. Quitarla deja la foto sin valoración.",
    edits_label: "Etiqueta (por ejemplo Rojo)",
    edits_keywords: "Palabras clave, separadas por comas",
    edits_save: "Guardar",
    edits_saved: "Guardado en Daguerre.",
    edits_recipe: "Receta de revelado",
    edits_no_recipe: "Sin ajustes de revelado.",
    recipe_exposure: "Exposición guardada de receta (EV)",
    recipe_wb_title: "Balance de blancos de la receta",
    recipe_wb_temperature: "Temperatura de receta (K)",
    recipe_wb_tint: "Matiz de receta",
    recipe_wb_absent: "Sin ajuste",
    recipe_wb_save: "Guardar cambios de balance",
    recipe_wb_clear_temperature: "Quitar sólo temperatura",
    recipe_wb_clear_tint: "Quitar sólo matiz",
    recipe_wb_help: "Temperatura de 2000 a 50000 K; matiz de −150 a +150, enteros. Vacío no es cero: usa Quitar para retirar un ajuste guardado. Guarda la receta para reveladores compatibles; Daguerre no renderiza estos ajustes en la vista previa. No son Kelvin medidos del JPEG/TIFF. La escritura XMP sigue el ajuste actual indicado debajo.",
    recipe_exposure_stored: "Valor guardado",
    recipe_exposure_absent: "Sin ajuste de exposición",
    recipe_exposure_save: "Guardar exposición",
    recipe_exposure_clear: "Quitar sólo exposición",
    recipe_exposure_help: "De −5 a +5 EV, dos decimales. Guarda este ajuste de receta sin generar una imagen ni cambiar el original. Conserva los demás ajustes. El control separado de exportación tiene rango de −3 a +3 EV.",
    sidecar_title: "Archivo .xmp",
    sidecar_none: "no hay ninguno junto a esta foto.",
    sidecar_by_daguerre: "escrito por Daguerre.",
    sidecar_by_foreign: "creado por otro programa; Daguerre lo ha leído y lo respeta.",
    sidecar_invalid: "no es un XMP válido; Daguerre no lo tocará.",
    sidecar_changed: "Ha cambiado en el disco desde que se leyó.",
    sidecar_shared_name: "Otro archivo de esta carpeta tiene el mismo nombre, así que el sidecar se llama <nombre de la foto>.<extensión>.xmp.",
    sidecar_reread: "Releer",
    sidecar_write: "Escribir .xmp",
    sidecar_write_off: "Activa «Escribir archivos .xmp» en Ajustes para poder escribirlo.",
    sidecar_written: "Guardado, y el archivo .xmp está al día.",
    imported_not_applied: (n: number) => `${n} ajustes importados que Daguerre no aplica`,
    settings_xmp_label: "Escribir archivos .xmp junto a las fotos editadas (desactivado por defecto)",
    settings_xmp_hint:
      "Las valoraciones, etiquetas, palabras clave y recetas de revelado se guardan en Daguerre. Con esto activado, además se guardan como archivos .xmp estándar junto a cada foto, para los reveladores RAW. La foto nunca se modifica, y un .xmp que ya exista se copia como respaldo y se fusiona, no se sustituye.",
  },
};

export function detectLang(): Lang {
  try {
    return navigator.language.toLowerCase().startsWith("es") ? "es" : "en";
  } catch {
    return "en";
  }
}

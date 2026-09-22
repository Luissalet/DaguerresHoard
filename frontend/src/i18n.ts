export type Lang = "en" | "es";

export interface Dict {
  appName: string;
  nav_library: string;
  nav_search: string;
  nav_duplicates: string;
  nav_timeline: string;
  nav_places: string;
  nav_albums: string;
  nav_settings: string;
  nav_activity: string;
  search_placeholder: string;
  search_button: string;
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
}

export const dict: Record<Lang, Dict> = {
  en: {
    appName: "Argus's Hoard",
    nav_library: "Library",
    nav_search: "Search",
    nav_duplicates: "Duplicates",
    nav_timeline: "Timeline",
    nav_places: "Places",
    nav_albums: "Albums",
    nav_settings: "Settings",
    nav_activity: "Assistant activity",
    search_placeholder: "Describe what you are looking for…",
    search_button: "Search",
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
    empty_search_body: "Try “sunset on the beach” or “whiteboard notes”. English works best.",
    no_results: "No photos matched your search.",
    loading: "Loading…",
    photos_count: (n: number) => `${n} photo${n === 1 ? "" : "s"}`,
    // B2 (live report): "50 photos / 262" read as "262 matches". Results
    // are ranked by similarity, not filtered -- this says so.
    ranked_count: (returned, total) => `the best ${returned} of ${total} photo${total === 1 ? "" : "s"}, ranked`,
    open_in_explorer: "Open in Explorer",
    similar_photos: "Similar photos",
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
      "Argus is using its colour-only fallback, so searches only understand colours. Download the image model in Settings to search by what is in your photos.",
    open_settings: "Open Settings",
    filter_from: "From",
    filter_to: "To",
    add_to_album: "Add to album",
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
      "Argus shares its models with Faustus and any other local app instead of loading its own copy: whatever is already running (Faustus, Ollama, llama.cpp, or another OpenAI-compatible server) is used first.",
    backend_row_vision: "Vision (captions)",
    backend_row_llm: "Language model (query translation)",
    backend_recheck: "Re-check",
    backend_resolved: "Available",
    backend_unavailable: "Not available",
    backend_faustus_url: "Faustus URL",
    backend_faustus_token: "Faustus token",
    backend_token_set: "Token saved",
    backend_token_placeholder: "Leave blank to keep the saved token",
    backend_override_url: "URL override",
    backend_override_model: "Model override",
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
  },
  es: {
    appName: "El Tesoro de Argos",
    nav_library: "Biblioteca",
    nav_search: "Buscar",
    nav_duplicates: "Duplicados",
    nav_timeline: "Cronología",
    nav_places: "Lugares",
    nav_albums: "Álbumes",
    nav_settings: "Ajustes",
    nav_activity: "Actividad del asistente",
    search_placeholder: "Describe lo que buscas…",
    search_button: "Buscar",
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
    empty_search_body: "Prueba «atardecer en la playa» o «notas en la pizarra». En inglés funciona mejor.",
    no_results: "Ninguna foto coincide con tu búsqueda.",
    loading: "Cargando…",
    photos_count: (n: number) => `${n} foto${n === 1 ? "" : "s"}`,
    ranked_count: (returned, total) =>
      `las ${returned} mejores de ${total} foto${total === 1 ? "" : "s"}, por similitud`,
    open_in_explorer: "Abrir en el Explorador",
    similar_photos: "Fotos similares",
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
      "Argos está usando su modo básico, que solo entiende colores. Descarga el modelo de imagen en Ajustes para buscar por lo que aparece en tus fotos.",
    open_settings: "Abrir Ajustes",
    filter_from: "Desde",
    filter_to: "Hasta",
    add_to_album: "Añadir a álbum",
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
      "Argos comparte sus modelos con Faustus y con cualquier otra app local en vez de cargar su propia copia: usa primero lo que ya esté en marcha (Faustus, Ollama, llama.cpp u otro servidor compatible con OpenAI).",
    backend_row_vision: "Visión (descripciones)",
    backend_row_llm: "Modelo de lenguaje (traducción de búsquedas)",
    backend_recheck: "Volver a comprobar",
    backend_resolved: "Disponible",
    backend_unavailable: "No disponible",
    backend_faustus_url: "URL de Faustus",
    backend_faustus_token: "Token de Faustus",
    backend_token_set: "Token guardado",
    backend_token_placeholder: "Déjalo en blanco para mantener el token guardado",
    backend_override_url: "URL manual",
    backend_override_model: "Modelo manual",
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
  },
};

export function detectLang(): Lang {
  try {
    return navigator.language.toLowerCase().startsWith("es") ? "es" : "en";
  } catch {
    return "en";
  }
}

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
    empty_search_body: "Try “sunset on the beach” or “whiteboard notes”.",
    no_results: "No photos matched your search.",
    loading: "Loading…",
    photos_count: (n: number) => `${n} photo${n === 1 ? "" : "s"}`,
    open_in_explorer: "Open in Explorer",
    similar_photos: "Similar photos",
    close: "Close",
    exact_duplicates: "Exact duplicates",
    near_duplicates: "Near duplicates",
    keeper: "Keeper",
    copy_paths: "Copy paths",
    copied: "Copied",
    on_this_day: "On this day",
    year: "Year",
    month_names: [
      "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ],
    roots: "Indexed folders",
    add_folder: "Add folder",
    folder_path_placeholder: "/absolute/path/to/photos",
    add: "Add",
    scan_now: "Scan now",
    scanning: "Scanning…",
    remove: "Remove",
    confirm_remove: "Remove this folder and its photos from the index?",
    yes_remove: "Yes, remove",
    cancel: "Cancel",
    model_status: "Embedding model",
    geocoder_status: "Places data",
    download_geonames: "Download full world cities dataset",
    ollama_url: "Ollama URL",
    ollama_model: "Ollama vision model",
    test_connection: "Test connection",
    connection_ok: "Connected",
    connection_failed: "Connection failed",
    save: "Save",
    saved: "Saved",
    albums_empty: "No albums yet. Select photos in the library and create one.",
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
    empty_search_body: "Prueba “atardecer en la playa” o “notas en pizarra”.",
    no_results: "Ninguna foto coincide con tu búsqueda.",
    loading: "Cargando…",
    photos_count: (n: number) => `${n} foto${n === 1 ? "" : "s"}`,
    open_in_explorer: "Abrir en el Explorador",
    similar_photos: "Fotos similares",
    close: "Cerrar",
    exact_duplicates: "Duplicados exactos",
    near_duplicates: "Duplicados aproximados",
    keeper: "Conservar",
    copy_paths: "Copiar rutas",
    copied: "Copiado",
    on_this_day: "Un día como hoy",
    year: "Año",
    month_names: [
      "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
    ],
    roots: "Carpetas indexadas",
    add_folder: "Añadir carpeta",
    folder_path_placeholder: "/ruta/absoluta/a/fotos",
    add: "Añadir",
    scan_now: "Escanear ahora",
    scanning: "Escaneando…",
    remove: "Quitar",
    confirm_remove: "¿Quitar esta carpeta y sus fotos del índice?",
    yes_remove: "Sí, quitar",
    cancel: "Cancelar",
    model_status: "Modelo de embeddings",
    geocoder_status: "Datos de lugares",
    download_geonames: "Descargar base de datos mundial de ciudades",
    ollama_url: "URL de Ollama",
    ollama_model: "Modelo de visión de Ollama",
    test_connection: "Probar conexión",
    connection_ok: "Conectado",
    connection_failed: "Conexión fallida",
    save: "Guardar",
    saved: "Guardado",
    albums_empty: "Aún no hay álbumes. Selecciona fotos en la biblioteca y crea uno.",
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
    theme_light: "Claro",
    theme_dark: "Oscuro",
    lang_switch: "EN",
    caption: "Descripción",
    generate_caption: "Generar descripción",
    generating: "Generando…",
    photo_details: "Detalles de la foto",
    taken: "Tomada",
    camera: "Cámara",
    lens: "Objetivo",
    exposure: "Exposición",
    path: "Ruta",
  },
};

export function detectLang(): Lang {
  try {
    return navigator.language.toLowerCase().startsWith("es") ? "es" : "en";
  } catch {
    return "en";
  }
}

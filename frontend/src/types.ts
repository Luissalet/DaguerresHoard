export interface Photo {
  id: string;
  path: string;
  taken_at: string | null;
  place: string | null;
  size: number;
  width: number | null;
  height: number | null;
  thumbnail_url: string;
  score?: number;
  n?: number;
  caption_match?: boolean;
  relevance?: "strong" | "medium" | "weak";
  // set when the photo is a key frame of a video
  video_id?: string;
  frame_ts?: number;
  timestamp?: string;
  video_name?: string;
}

export interface PhotoDetail extends Photo {
  make?: string;
  model?: string;
  lens?: string;
  f_number?: number;
  exposure_time?: string;
  iso?: number;
  focal_length?: number;
  orientation?: number;
  gps_lat?: number;
  gps_lon?: number;
  region?: string;
  country?: string;
  city?: string;
  caption?: string;
  caption_error?: string;
  date_source?: "exif" | "file_mtime";
  missing?: boolean;
  edits?: PhotoEdits;
}

export interface SidecarWrite {
  written: boolean;
  path?: string;
  created?: boolean;
  merged?: boolean;
  backup_of_original?: string;
  reason?: string;
  error?: string;
}

// rating, label, keywords and the develop recipe of one photo, and the state of its .xmp sidecar
export interface PhotoEdits {
  photo_id: string;
  rating: number | null;
  label: string | null;
  keywords: string[] | null;
  recipe: Record<string, unknown>;
  source: "daguerre" | "sidecar" | "embedded" | null;
  sidecar: { path: string; exists: boolean; changed_on_disk?: boolean; written_by?: "daguerre" | "foreign" | "invalid" };
  write_sidecars: boolean;
  imported_not_applied?: { source: string; crs: Record<string, unknown> };
  sidecar_write?: SidecarWrite;
  read?: string;
  note?: string;
}

export interface SearchResult {
  query?: string | null;
  mode?: "filtered_listing";
  count: number;
  returned: number;
  indexed_total: number;
  results: Photo[];
  has_more: boolean;
  next_offset?: number | null;
  embedder?: string;
  note?: string;
  note_codes?: string[];
  translated_query?: string;
  original_query?: string;
  translate_error?: string;
}

export interface PhotoListResult {
  count: number;
  results: Photo[];
  truncated: boolean;
  next_offset: number | null;
}

export interface Root {
  id: number;
  path: string;
  excluded_globs: string[];
  created_at: string;
  added_by: string;
  photo_count: number;
  exists: boolean;
}

export interface JobStats {
  files_seen?: number;
  new?: number;
  updated?: number;
  moved?: number;
  unchanged?: number;
  embedded?: number;
  errors?: number;
  error_samples?: string[];
}

export interface Job {
  id: string;
  kind: string;
  status: "running" | "done" | "error" | "interrupted";
  progress: number;
  message: string | null;
  stats: JobStats | null;
  started_at: string;
  finished_at: string | null;
}

export interface LibraryStatus {
  roots: Root[];
  photo_count: number;
  missing_count: number;
  video_count: number;
  frame_count: number;
  embedder: { name: string; dim: number; semantic: boolean; stale_photos: number };
  geocoder_source: string;
  heic_support: boolean;
  indexing: boolean;
  recent_jobs: Job[];
  ollama: { base_url: string; model: string };
}

export interface ModelStatus {
  active: string;
  clip_downloaded: boolean;
  cache_bytes: number;
  download_size_hint_mb: number;
  downloading: boolean;
}

export interface DuplicateGroup {
  kind: "exact" | "near";
  keeper_id: string;
  max_distance: number;
  reclaimable_bytes: number;
  photos: Photo[];
}

export interface DuplicatesResult {
  kind: string;
  count: number;
  total_groups: number;
  has_more: boolean;
  reclaimable_bytes_total: number;
  groups: DuplicateGroup[];
}

export interface TimelineResult {
  years: Record<string, number>;
  months: Record<string, Record<string, number>>;
  on_this_day: { id: string; taken_at: string; place: string | null; thumbnail_url: string }[];
  on_this_day_count: number;
  samples?: Record<string, string[]>;
}

export interface Album {
  id: string;
  name: string;
  created_at: string;
  created_by?: string;
  photo_count: number;
  cover_thumbnail_url?: string | null;
  photos?: Photo[];
}

export interface ResolutionInfo {
  capability: string;
  provider: string | null;
  url: string | null;
  model: string | null;
  api: string | null;
  state: "resolved" | "unavailable";
  reason: string;
  details?: Record<string, unknown>;
}

export interface BackendStatus {
  llm: ResolutionInfo;
  vision: ResolutionInfo;
  embeddings: ResolutionInfo;
  tts: ResolutionInfo;
  stt: ResolutionInfo;
  image: ResolutionInfo;
  video: ResolutionInfo;
  music: ResolutionInfo;
  token_set: boolean;
  overrides: {
    faustus_url: string;
    vision: { url: string; model: string };
    llm: { url: string; model: string };
  };
  config_error: string | null;
  used_capabilities: string[];
  image_search: { engine: string; active: string; semantic: boolean };
}

export interface BackendConfigInput {
  faustus_url?: string;
  faustus_token?: string;
  vision_url?: string;
  vision_model?: string;
  llm_url?: string;
  llm_model?: string;
}

export interface AgentCall {
  id: number;
  tool: string;
  args_summary: string;
  ok: number;
  duration_ms: number;
  error: string | null;
  created_at: string;
}

export interface VideoSummary {
  id: string;
  path: string;
  name: string;
  taken_at: string | null;
  size: number;
  duration: number | null;
  duration_label: string | null;
  width: number | null;
  height: number | null;
  frame_count: number;
  status: "ok" | "no_extractor" | "error";
  error?: string;
  thumbnail_url: string | null;
  stream_url: string;
}

export interface VideoFrame {
  id: string;
  ts: number;
  timestamp: string;
  width: number | null;
  height: number | null;
  caption: string | null;
  thumbnail_url: string;
}

export interface VideoDetail extends VideoSummary {
  frames: VideoFrame[];
}

export interface VideoListResult {
  count: number;
  returned: number;
  results: VideoSummary[];
  has_more: boolean;
  next_offset?: number;
  note?: string;
}

/** A key frame as the Photo the grid and the lightbox work with. */
export function frameAsPhoto(video: VideoSummary, f: VideoFrame): Photo {
  return {
    id: f.id,
    path: video.path,
    taken_at: video.taken_at,
    place: null,
    size: 0,
    width: f.width,
    height: f.height,
    thumbnail_url: f.thumbnail_url,
    video_id: video.id,
    frame_ts: f.ts,
    timestamp: f.timestamp,
    video_name: video.name,
  };
}

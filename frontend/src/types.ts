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
}

export interface SearchResult {
  query?: string;
  count: number;
  results: Photo[];
  has_more: boolean;
  embedder: string;
  note?: string;
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

export interface AgentCall {
  id: number;
  tool: string;
  args_summary: string;
  ok: number;
  duration_ms: number;
  error: string | null;
  created_at: string;
}

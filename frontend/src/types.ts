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
}

export interface PhotoDetail extends Photo {
  make?: string | null;
  model?: string | null;
  lens?: string | null;
  f_number?: number | null;
  exposure_time?: string | null;
  iso?: number | null;
  focal_length?: number | null;
  orientation?: number | null;
  gps_lat?: number | null;
  gps_lon?: number | null;
  region?: string | null;
  country?: string | null;
  city?: string | null;
  caption?: string | null;
  date_source?: string | null;
  content_hash?: string | null;
  indexed_at?: string | null;
}

export interface SearchResult {
  query: string;
  count: number;
  results: Photo[];
  truncated: boolean;
  contact_sheet_jpeg_base64: string | null;
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
}

export interface Job {
  id: string;
  kind: string;
  status: "running" | "done" | "error";
  progress: number;
  message: string;
  stats: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface LibraryStatus {
  roots: Root[];
  photo_count: number;
  missing_count: number;
  embedder: { name: string; dim: number };
  geocoder_source: string;
  recent_jobs: Job[];
  ollama: { base_url: string; model: string };
}

export interface DuplicateGroup {
  kind: "exact" | "near";
  keeper_id: string;
  max_distance: number;
  photos: Photo[];
}

export interface DuplicatesResult {
  kind: string;
  count: number;
  groups: DuplicateGroup[];
}

export interface TimelineResult {
  years: Record<string, Record<string, number>>;
  on_this_day: { id: string; taken_at: string; place: string | null }[];
  year?: Record<string, number>;
}

export interface Album {
  id: string;
  name: string;
  created_at: string;
  photo_count?: number;
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

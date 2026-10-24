import type {
  Album,
  AlbumAddResult,
  AgentCall,
  BackendConfigInput,
  BackendStatus,
  DuplicatesResult,
  Job,
  LibraryStatus,
  ModelStatus,
  PhotoDetail,
  PhotoEdits,
  PhotoListResult,
  Root,
  SearchResult,
  TimelineResult,
  VideoDetail,
  VideoListResult,
} from "./types";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!resp.ok) {
    let code = "error";
    let message = resp.statusText;
    try {
      const body = await resp.json();
      code = body.error ?? code;
      message = body.message ?? message;
    } catch {
      // not JSON: keep the status text
    }
    throw new ApiError(code, message);
  }
  return resp.json() as Promise<T>;
}

const post = <T>(path: string, body: unknown = {}) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

export type Params = Record<string, string | number | boolean | undefined>;

export interface CraftEngineStatus {
  engines: Record<string, { available: boolean; executable: string | null; capability: string }>;
}
export interface CraftArtifact {
  id: string;
  engine: string;
  output_url?: string;
  preview_url?: string;
  native_format?: string;
  original_modified?: boolean;
}

export interface ReferenceMatchResult {
  id: string;
  manifest_url: string;
  photos: { n: number; id: string; path: string; output_url: string }[];
  omitted: { id: string; reason: string }[];
}

export interface SelectionExportResult {
  id: string;
  title: string;
  requested: number;
  returned: number;
  complete: boolean;
  omitted: { id: string; requested_n: number; reason: string }[];
}

function qs(params: Params): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") q.set(k, String(v));
  return q.toString();
}

export const api = {
  exportSelection: (ids: string[], title: string) => post<SelectionExportResult>("/photos/api/photos/export", { ids, title }),
  matchReference: (reference_id: string, ids: string[], strength: number) => post<ReferenceMatchResult>("/photos/api/photos/match-reference", { reference_id, ids, strength }),
  craftStatus: () => request<CraftEngineStatus>("/photos/api/image-engine/status"),
  craftFromPhoto: (photo_id: string) => post<CraftArtifact>("/photos/api/image-engine/from-photo", { photo_id }),
  craftDevelop: (photo_id: string, exposure: number) => post<CraftArtifact>("/photos/api/image-engine/develop", { photo_id, exposure, output_format: "png" }),
  imageOpenEditor: (artifact_id: string, engine: string) => post<{ pid: number }>("/photos/api/image-engine/editor", { artifact_id, engine }),
  libraryStatus: () => request<LibraryStatus>("/photos/api/library"),
  places: () =>
    request<{
      countries: Record<string, { city: string; count: number; sample_thumbnail_url: string }[]>;
      approximate_count: number;
      note?: string;
    }>("/photos/api/places"),
  listPhotos: (params: Params) => request<PhotoListResult>(`/photos/api/photos?${qs(params)}`),
  getPhoto: (id: string) => request<PhotoDetail>(`/photos/api/photos/${id}`),
  caption: (id: string) => post<PhotoDetail>(`/photos/api/photos/${id}/caption`),
  getEdits: (id: string) => request<PhotoEdits>(`/photos/api/photos/${id}/edits`),
  setEdits: (
    id: string,
    body: { rating?: number | null; label?: string | null; keywords?: string[] | null; recipe?: Record<string, unknown> | null },
  ) => request<PhotoEdits>(`/photos/api/photos/${id}/edits`, { method: "PUT", body: JSON.stringify(body) }),
  readSidecar: (id: string) => post<PhotoEdits>(`/photos/api/photos/${id}/sidecar/read`),
  writeSidecar: (id: string) => post<PhotoEdits>(`/photos/api/photos/${id}/sidecar/write`),
  previewUrl: (id: string, size = 1600) => `/photos/api/photos/${id}/preview?size=${size}`,
  openInExplorer: (id: string) => post<{ ok: boolean }>(`/photos/api/photos/${id}/open`),
  addRoot: (path: string, excluded_globs: string[] = []) => post<Root>("/photos/api/roots", { path, excluded_globs }),
  updateRoot: (id: number, excluded_globs: string[]) =>
    request<Root>(`/photos/api/roots/${id}`, { method: "PUT", body: JSON.stringify({ excluded_globs }) }),
  removeRoot: (id: number) => request<{ ok: boolean }>(`/photos/api/roots/${id}`, { method: "DELETE" }),
  startScan: (root_id?: number) => post<{ job_id: string }>("/photos/api/scan", { root_id }),
  getJob: (id: string) => request<Job>(`/photos/api/jobs/${id}`),
  search: (query: string, filters: Record<string, unknown>, limit = 50) =>
    post<SearchResult>("/photos/api/search", { query, filters, limit }),
  similar: (photo_id: string, limit = 12) => post<SearchResult>("/photos/api/similar", { photo_id, limit }),
  duplicates: (kind: "exact" | "near", limit = 50) => post<DuplicatesResult>("/photos/api/duplicates", { kind, limit }),
  listVideos: (params: Params = {}) => request<VideoListResult>(`/photos/api/videos?${qs(params)}`),
  getVideo: (id: string) => request<VideoDetail>(`/photos/api/videos/${id}`),
  videoStreamUrl: (id: string) => `/photos/api/videos/${id}/stream`,
  timeline: () => request<TimelineResult>("/photos/api/timeline?samples=4"),
  listAlbums: () => request<Album[]>("/photos/api/albums"),
  getAlbum: (id: string) => request<Album>(`/photos/api/albums/${id}`),
  albumAdd: (name: string, photo_ids: string[]) => post<AlbumAddResult>("/photos/api/albums", { name, photo_ids }),
  albumRemove: (id: string, photo_ids: string[]) => post<Album>(`/photos/api/albums/${id}/remove`, { photo_ids }),
  deleteAlbum: (id: string) => request<{ ok: boolean }>(`/photos/api/albums/${id}`, { method: "DELETE" }),
  getSettings: () =>
    request<{ ollama_base_url: string; ollama_model: string; translate_search: boolean; xmp_sidecars: boolean }>("/photos/api/settings"),
  setSettings: (body: { ollama_base_url?: string; ollama_model?: string; translate_search?: boolean; xmp_sidecars?: boolean }) =>
    post<{ ollama_base_url: string; ollama_model: string; translate_search: boolean; xmp_sidecars: boolean }>("/photos/api/settings", body),
  testOllama: () => post<{ ok: boolean; error: string | null }>("/photos/api/settings/ollama/test"),
  captionBatch: (limit = 500) => post<{ job_id: string }>("/photos/api/captions/batch", { limit }),
  modelStatus: () => request<ModelStatus>("/photos/api/model"),
  downloadModel: () => post<{ job_id: string }>("/photos/api/model/download"),
  downloadGeocoder: () => post<{ job_id: string }>("/photos/api/geocoder/download"),
  agentCalls: (limit = 50) => request<AgentCall[]>(`/photos/api/agent-calls?limit=${limit}`),
  getBackend: () => request<BackendStatus>("/photos/api/backend"),
  setBackendConfig: (body: BackendConfigInput) =>
    request<BackendStatus>("/photos/api/backend/config", { method: "PUT", body: JSON.stringify(body) }),
  recheckBackend: () => post<BackendStatus>("/photos/api/backend/recheck"),
};

export function errorText(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return String(e);
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export function fileName(path: string): string {
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] || path;
}

// A2 (live report): exact-duplicate tiles showed only the file name, which
// is identical within a group, so the folder that tells the copies apart
// was visible only in the hover title.
export function parentFolder(path: string): string {
  // Re-walk: a camera roll's "07" said nothing next to "Copia movil 2024";
  // climb past year/month folders to the first named one ("Camera
  // Roll/2024/07").
  const parts = path.split(/[\\/]/).filter(Boolean).slice(0, -1);
  const out: string[] = [];
  while (parts.length) {
    const seg = parts.pop() as string;
    out.unshift(seg);
    if (!/^\d+$/.test(seg)) break;
  }
  return out.join("/");
}

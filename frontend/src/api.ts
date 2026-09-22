import type {
  Album,
  AgentCall,
  BackendConfigInput,
  BackendStatus,
  DuplicatesResult,
  Job,
  LibraryStatus,
  ModelStatus,
  PhotoDetail,
  PhotoListResult,
  Root,
  SearchResult,
  TimelineResult,
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

function qs(params: Params): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") q.set(k, String(v));
  return q.toString();
}

export const api = {
  libraryStatus: () => request<LibraryStatus>("/api/library"),
  places: () =>
    request<{
      countries: Record<string, { city: string; count: number; sample_thumbnail_url: string }[]>;
      approximate_count: number;
      note?: string;
    }>("/api/places"),
  listPhotos: (params: Params) => request<PhotoListResult>(`/api/photos?${qs(params)}`),
  getPhoto: (id: string) => request<PhotoDetail>(`/api/photos/${id}`),
  caption: (id: string) => post<PhotoDetail>(`/api/photos/${id}/caption`),
  previewUrl: (id: string, size = 1600) => `/api/photos/${id}/preview?size=${size}`,
  openInExplorer: (id: string) => post<{ ok: boolean }>(`/api/photos/${id}/open`),
  addRoot: (path: string, excluded_globs: string[] = []) => post<Root>("/api/roots", { path, excluded_globs }),
  updateRoot: (id: number, excluded_globs: string[]) =>
    request<Root>(`/api/roots/${id}`, { method: "PUT", body: JSON.stringify({ excluded_globs }) }),
  removeRoot: (id: number) => request<{ ok: boolean }>(`/api/roots/${id}`, { method: "DELETE" }),
  startScan: (root_id?: number) => post<{ job_id: string }>("/api/scan", { root_id }),
  getJob: (id: string) => request<Job>(`/api/jobs/${id}`),
  search: (query: string, filters: Record<string, unknown>, limit = 50) =>
    post<SearchResult>("/api/search", { query, filters, limit }),
  similar: (photo_id: string, limit = 12) => post<SearchResult>("/api/similar", { photo_id, limit }),
  duplicates: (kind: "exact" | "near", limit = 50) => post<DuplicatesResult>("/api/duplicates", { kind, limit }),
  timeline: () => request<TimelineResult>("/api/timeline?samples=4"),
  listAlbums: () => request<Album[]>("/api/albums"),
  getAlbum: (id: string) => request<Album>(`/api/albums/${id}`),
  albumAdd: (name: string, photo_ids: string[]) => post<Album>("/api/albums", { name, photo_ids }),
  albumRemove: (id: string, photo_ids: string[]) => post<Album>(`/api/albums/${id}/remove`, { photo_ids }),
  deleteAlbum: (id: string) => request<{ ok: boolean }>(`/api/albums/${id}`, { method: "DELETE" }),
  getSettings: () =>
    request<{ ollama_base_url: string; ollama_model: string; translate_search: boolean }>("/api/settings"),
  setSettings: (body: { ollama_base_url?: string; ollama_model?: string; translate_search?: boolean }) =>
    post<{ ollama_base_url: string; ollama_model: string; translate_search: boolean }>("/api/settings", body),
  testOllama: () => post<{ ok: boolean; error: string | null }>("/api/settings/ollama/test"),
  captionBatch: (limit = 500) => post<{ job_id: string }>("/api/captions/batch", { limit }),
  modelStatus: () => request<ModelStatus>("/api/model"),
  downloadModel: () => post<{ job_id: string }>("/api/model/download"),
  downloadGeocoder: () => post<{ job_id: string }>("/api/geocoder/download"),
  agentCalls: (limit = 50) => request<AgentCall[]>(`/api/agent-calls?limit=${limit}`),
  getBackend: () => request<BackendStatus>("/api/backend"),
  setBackendConfig: (body: BackendConfigInput) =>
    request<BackendStatus>("/api/backend/config", { method: "PUT", body: JSON.stringify(body) }),
  recheckBackend: () => post<BackendStatus>("/api/backend/recheck"),
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

import type {
  Album,
  AgentCall,
  DuplicatesResult,
  Job,
  LibraryStatus,
  PhotoDetail,
  PhotoListResult,
  Root,
  SearchResult,
  TimelineResult,
} from "./types";

class ApiError extends Error {
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
      const detail = body.detail ?? body;
      code = detail.error ?? code;
      message = detail.message ?? message;
    } catch {
      // ignore JSON parse failures, fall back to statusText
    }
    throw new ApiError(code, message);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

export const api = {
  health: () => request<{ service: string; name: string; version: string; status: string }>("/api/health"),
  libraryStatus: () => request<LibraryStatus>("/api/library"),
  places: () =>
    request<{ countries: Record<string, { city: string; count: number; sample_thumbnail_url: string }[]> }>(
      "/api/places",
    ),
  listPhotos: (params: Record<string, string | number | boolean | undefined>) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") qs.set(k, String(v));
    return request<PhotoListResult>(`/api/photos?${qs.toString()}`);
  },
  getPhoto: (id: string) => request<PhotoDetail>(`/api/photos/${id}`),
  openInExplorer: (id: string) => request<{ ok: boolean }>(`/api/photos/${id}/open`, { method: "POST" }),
  listRoots: () => request<Root[]>("/api/roots"),
  addRoot: (path: string, excluded_globs: string[] = []) =>
    request<Root>("/api/roots", { method: "POST", body: JSON.stringify({ path, excluded_globs }) }),
  removeRoot: (id: number) => request<{ ok: boolean }>(`/api/roots/${id}`, { method: "DELETE" }),
  startScan: (root_id?: number) =>
    request<{ job_id: string }>("/api/scan", { method: "POST", body: JSON.stringify({ root_id }) }),
  getJob: (id: string) => request<Job>(`/api/jobs/${id}`),
  listJobs: () => request<Job[]>("/api/jobs"),
  search: (query: string, filters: Record<string, unknown>, limit = 60) =>
    request<SearchResult>("/api/agent/photos_search", {
      method: "POST",
      body: JSON.stringify({ query, filters, limit, contact_sheet: false }),
    }),
  similar: (photo_id: string, limit = 24) =>
    request<SearchResult>("/api/agent/photos_similar", {
      method: "POST",
      body: JSON.stringify({ photo_id, limit, contact_sheet: false }),
    }),
  describe: (photo_id: string, caption = false) =>
    request<PhotoDetail & { caption_error?: string }>("/api/agent/photos_describe", {
      method: "POST",
      body: JSON.stringify({ photo_id, caption }),
    }),
  duplicates: (kind: "exact" | "near", limit = 20) =>
    request<DuplicatesResult>("/api/agent/photos_duplicates", {
      method: "POST",
      body: JSON.stringify({ kind, limit }),
    }),
  timeline: (year?: number) =>
    request<TimelineResult>("/api/agent/photos_timeline", { method: "POST", body: JSON.stringify({ year }) }),
  listAlbums: () => request<Album[]>("/api/albums"),
  getAlbum: (id: string) => request<Album>(`/api/albums/${id}`),
  createAlbum: (name: string, photo_ids: string[]) =>
    request<Album>("/api/albums", { method: "POST", body: JSON.stringify({ name, photo_ids }) }),
  getSettings: () => request<{ ollama_base_url: string; ollama_model: string }>("/api/settings"),
  setSettings: (body: { ollama_base_url?: string; ollama_model?: string }) =>
    request<{ ollama_base_url: string; ollama_model: string }>("/api/settings", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  testOllama: () => request<{ ok: boolean; error: string | null }>("/api/settings/ollama/test", { method: "POST" }),
  downloadGeocoder: () => request<{ job_id: string }>("/api/geocoder/download", { method: "POST" }),
  agentCalls: (limit = 30) => request<AgentCall[]>(`/api/agent-calls?limit=${limit}`),
};

export { ApiError };

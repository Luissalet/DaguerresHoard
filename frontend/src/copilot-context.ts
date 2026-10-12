// What the shared assistant panel asks this app for: the real objects open in the current view and the unsaved form
// fields, plus a way to refresh the open view in place when the assistant finishes a turn. Nothing here renders anything
// and nothing here imports the API client, so it runs under `node --test` as it is.

export const CONTEXT_EVENT = "daguerre:context-request";
export const TURN_END_EVENT = "hoard:copilot-turn-end";

export interface EditorSnapshot {
  kind: string;
  object_id: string | null;
  dirty: boolean;
  fields: Record<string, unknown>;
}

export interface OpenState {
  page: string;
  photo: { id: string; name: string; video_id?: string; video_name?: string; timestamp?: string } | null;
  album: string | null;
  video: string | null;
  search: Record<string, unknown> | null;
}

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

export interface ContextDeps {
  getPhoto: (id: string) => Promise<Json>;
  getEdits: (id: string) => Promise<Json>;
  getAlbum: (id: string) => Promise<Json>;
  getVideo: (id: string) => Promise<Json>;
}

export interface CopilotContext {
  project?: { external_project_id: string; title: string };
  active_objects: Json[];
  view: Json;
}

// ---- forms ---------------------------------------------------------------------------------------------------------

// Fields of `draft` whose value differs from `initial` (compared as JSON, so arrays and "" clears count).
export function changedFields(initial: Json | null | undefined, draft: Json | null | undefined): Json {
  const base = initial || {};
  return Object.fromEntries(Object.entries(draft || {}).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(base[key])));
}

// A refreshed baseline arrives while the user is editing: fields the user did not touch follow the new baseline, touched ones stay.
export function rebaseForm<T extends Json>(previousBase: T | null | undefined, nextBase: T, form: T): T {
  const out: Json = { ...nextBase };
  for (const key of Object.keys(form)) {
    if (JSON.stringify(form[key]) !== JSON.stringify(previousBase?.[key])) out[key] = form[key];
  }
  return out as T;
}

export function parseKeywords(text: string): string[] {
  return String(text || "")
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean);
}

// The setEdits body for the fields the user changed: label as text, keywords as a list. Nothing else is sent.
export function editsPatch(changed: Json): { label?: string; keywords?: string[] } {
  const patch: { label?: string; keywords?: string[] } = {};
  if ("label" in changed) patch.label = String(changed.label ?? "");
  if ("keywords" in changed) patch.keywords = parseKeywords(String(changed.keywords ?? ""));
  return patch;
}

// Every open form answers this event with a snapshot of what the user has typed: { kind, object_id, dirty, fields }.
export function collectEditors(target: EventTarget | undefined = globalThis.window): EditorSnapshot[] {
  const found: EditorSnapshot[] = [];
  if (!target?.dispatchEvent) return found;
  target.dispatchEvent(
    new CustomEvent(CONTEXT_EVENT, {
      detail: {
        provide: (snapshot: EditorSnapshot | null) => {
          if (snapshot) found.push(snapshot);
        },
      },
    }),
  );
  return found;
}

// ---- what is open --------------------------------------------------------------------------------------------------

const state: OpenState = { page: "library", photo: null, album: null, video: null, search: null };

export function setPage(page: string) {
  state.page = page;
}

// Register what a component shows; the returned function clears it only if nobody replaced it meanwhile.
export function registerOpen<K extends "photo" | "album" | "video" | "search">(key: K, value: NonNullable<OpenState[K]>): () => void {
  state[key] = value as never;
  return () => {
    if (state[key] === (value as never)) state[key] = null as never;
  };
}

export function openState(): OpenState {
  return { ...state };
}

// ---- context -------------------------------------------------------------------------------------------------------

async function safe<T>(fn: () => Promise<T>): Promise<T | null> {
  try {
    return await fn();
  } catch {
    return null;
  }
}

const clip = (text: unknown, n: number) => {
  const s = String(text ?? "").replace(/\s+/g, " ").trim();
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
};
const base = (path: unknown) => String(path ?? "").split(/[\\/]/).filter(Boolean).pop() || "";
const pick = (source: Json | null | undefined, keys: string[]): Json =>
  Object.fromEntries(keys.filter((k) => source?.[k] !== undefined && source[k] !== null && source[k] !== "").map((k) => [k, source![k]]));

const MAX_ALBUM_PHOTOS = 20;
const MAX_KEYWORDS = 20;

function photoObject(photo: Json, edits: Json | null): Json {
  const out: Json = {
    kind: "photo",
    object_id: photo.id,
    title: base(photo.path) || photo.id,
    ...pick(photo, ["taken_at", "place", "width", "height"]),
  };
  if (photo.caption) out.caption = clip(photo.caption, 240);
  if (photo.video_id) out.video_id = photo.video_id;
  if (photo.timestamp) out.timestamp = photo.timestamp;
  if (edits) {
    if (edits.rating !== null && edits.rating !== undefined) out.rating = edits.rating;
    if (edits.label) out.label = edits.label;
    if (Array.isArray(edits.keywords) && edits.keywords.length) out.keywords = edits.keywords.slice(0, MAX_KEYWORDS);
  }
  return out;
}

function albumObject(album: Json): Json {
  const photos: Json[] = Array.isArray(album.photos) ? album.photos : [];
  return {
    kind: "album",
    object_id: album.id,
    title: album.name || album.id,
    photo_count: album.photo_count ?? photos.length,
    ...(album.created_by ? { created_by: album.created_by } : {}),
    photo_ids: photos.slice(0, MAX_ALBUM_PHOTOS).map((p) => p.id),
  };
}

function videoObject(video: Json): Json {
  return {
    kind: "video",
    object_id: video.id,
    title: video.name || base(video.path) || video.id,
    ...pick(video, ["duration_label", "taken_at", "frame_count", "width", "height"]),
  };
}

// Pure core (dependencies injected so it can be tested): never throws; unknown ids yield no object.
export async function buildContext(deps: ContextDeps, open: OpenState, editors: EditorSnapshot[] = []): Promise<CopilotContext> {
  const active: Json[] = [];
  const seen = new Set<string>();
  const add = (object: Json) => {
    const key = `${object.kind}:${object.object_id}`;
    if (!seen.has(key)) {
      seen.add(key);
      active.push(object);
    }
  };
  const realId = (id: unknown): string | null => (typeof id === "string" && id && id !== "new" ? id : null);

  let project: CopilotContext["project"];
  let viewObject: string | undefined;

  const albumId = realId(open.album);
  if (albumId) {
    const album = await safe(() => deps.getAlbum(albumId));
    if (album?.id) {
      project = { external_project_id: String(album.id), title: String(album.name || album.id) };
      add(albumObject(album));
      viewObject = String(album.id);
    }
  }

  const videoId = realId(open.video) || realId(open.photo?.video_id);
  if (videoId) {
    const video = await safe(() => deps.getVideo(videoId));
    if (video?.id) {
      add(videoObject(video));
      if (!viewObject) viewObject = String(video.id);
    }
  }

  const photoId = realId(open.photo?.id);
  if (photoId) {
    const [photo, edits] = await Promise.all([safe(() => deps.getPhoto(photoId)), safe(() => deps.getEdits(photoId))]);
    if (photo?.id) {
      add(photoObject(photo, open.photo?.video_id ? null : edits));
      viewObject = String(photo.id);
    }
  }

  // an open edit form of a photo that is not (or no longer) the open one still names a real photo
  for (const e of editors) {
    const id = realId(e.object_id);
    if (e.kind !== "photo-edits" || !id || seen.has(`photo:${id}`)) continue;
    const [photo, edits] = await Promise.all([safe(() => deps.getPhoto(id)), safe(() => deps.getEdits(id))]);
    if (photo?.id) add(photoObject(photo, edits));
  }

  const view: Json = { page: open.page };
  if (viewObject) view.object_id = viewObject;
  if (open.page === "search" && open.search) view.search = open.search;
  const editor = editors.find((e) => e.dirty) || editors[0];
  if (editor) view.editor = editor;
  if (editors.length > 1) view.editors = editors;
  const out: CopilotContext = { active_objects: active, view };
  if (project) out.project = project;
  return out;
}

let contextDeps: ContextDeps | null = null;

export function context(): Promise<CopilotContext> {
  if (!contextDeps) return Promise.resolve({ active_objects: [], view: { page: state.page } });
  return buildContext(contextDeps, openState(), collectEditors()).catch(() => ({ active_objects: [], view: { page: state.page } }));
}

// ---- refresh when the assistant finishes a turn -------------------------------------------------------------------

const handlers = new Set<() => void>();
let timer: ReturnType<typeof setTimeout> | undefined;
export const REFRESH_DEBOUNCE_MS = 250;

// Every mounted view registers what "reload what is on screen" means (it keeps the forms the user is editing untouched).
export function onRefresh(fn: () => void): () => void {
  handlers.add(fn);
  return () => {
    handlers.delete(fn);
  };
}

function scheduleRefresh() {
  clearTimeout(timer);
  timer = setTimeout(() => {
    for (const fn of [...handlers]) {
      try {
        fn();
      } catch {
        // a refresh must never break the page
      }
    }
  }, REFRESH_DEBOUNCE_MS);
}

export const onTurnEnd = () => scheduleRefresh();

// Once at start: the object the launcher looks for, and the window event it dispatches on turn end (the debounce merges the two).
export function installCopilot(deps: ContextDeps, target: (EventTarget & { hoardCopilot?: unknown }) | undefined = globalThis.window) {
  if (!target || target.hoardCopilot) return;
  contextDeps = deps;
  target.hoardCopilot = { context, onTurnEnd };
  target.addEventListener(TURN_END_EVENT, scheduleRefresh);
}

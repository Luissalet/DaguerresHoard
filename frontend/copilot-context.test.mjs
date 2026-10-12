import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildContext, changedFields, collectEditors, editsPatch, installCopilot, onRefresh, openState, parseKeywords, rebaseForm, registerOpen,
  setPage, CONTEXT_EVENT, TURN_END_EVENT,
} from "./src/copilot-context.ts";

const photos = {
  p1: { id: "p1", path: "C:\\Photos\\2024\\Lisbon\\IMG_1.jpg", taken_at: "2024-07-01T10:00:00", place: "Lisbon", width: 4000, height: 3000, caption: "A tram " + "x".repeat(400) },
  f1: { id: "f1", path: "C:\\Videos\\trip.mp4", video_id: "v1", timestamp: "00:12", width: 640, height: 360 },
};
const edits = { p1: { rating: 4, label: "Blue", keywords: ["tram", "city"], recipe: {}, sidecar: { path: "x.xmp" } } };
const album = { id: "a1", name: "Trip", photo_count: 25, created_by: "agent", photos: Array.from({ length: 25 }, (_, i) => ({ id: `p${i}` })) };
const video = { id: "v1", name: "trip.mp4", path: "C:\\Videos\\trip.mp4", duration_label: "0:30", frame_count: 3, frames: [{ id: "f1" }] };
const deps = {
  getPhoto: async (id) => { if (!photos[id]) throw new Error("404"); return photos[id]; },
  getEdits: async (id) => { if (!edits[id]) throw new Error("404"); return edits[id]; },
  getAlbum: async (id) => { if (id !== "a1") throw new Error("404"); return album; },
  getVideo: async (id) => { if (id !== "v1") throw new Error("404"); return video; },
};
const none = { page: "library", photo: null, album: null, video: null, search: null };

test("only the fields the user changed are sent, including manual clears", () => {
  assert.deepEqual(changedFields({ label: "A", keywords: "a" }, { label: "", keywords: "a" }), { label: "" });
  assert.deepEqual(changedFields(null, { label: "x" }), { label: "x" });
  assert.deepEqual(parseKeywords(" a, b ,,c "), ["a", "b", "c"]);
  assert.deepEqual(editsPatch({ keywords: "a, b" }), { keywords: ["a", "b"] });
  assert.deepEqual(editsPatch({ label: "" }), { label: "" });
  assert.deepEqual(editsPatch({ rating: 5, other: 1 }), {});
});

test("a reload keeps what the user typed and updates the rest", () => {
  const before = { label: "Old", keywords: "a" };
  const typed = { label: "Old", keywords: "a, b" };
  const after = { label: "Agent label", keywords: "a" };
  assert.deepEqual(rebaseForm(before, after, typed), { label: "Agent label", keywords: "a, b" });
  // the agent's label survives saving the user's keywords: only keywords differs from the loaded baseline
  assert.deepEqual(editsPatch(changedFields(before, typed)), { keywords: ["a", "b"] });
});

test("photo view returns the real photo, its edits, a short caption and the editor", async () => {
  const editors = [{ kind: "photo-edits", object_id: "p1", dirty: true, fields: { label: "Red" } }];
  const ctx = await buildContext(deps, { ...none, page: "library", photo: { id: "p1", name: "IMG_1.jpg" } }, editors);
  assert.deepEqual(ctx.active_objects.map((o) => `${o.kind}:${o.object_id}`), ["photo:p1"]);
  const photo = ctx.active_objects[0];
  assert.equal(photo.title, "IMG_1.jpg");
  assert.equal(photo.rating, 4);
  assert.deepEqual(photo.keywords, ["tram", "city"]);
  assert.ok(photo.caption.length <= 240);
  assert.equal(photo.place, "Lisbon");
  assert.equal(ctx.view.object_id, "p1");
  assert.deepEqual(ctx.view.editor.fields, { label: "Red" });
  assert.equal(ctx.project, undefined);
});

test("an open album is the project and lists a bounded number of photo ids", async () => {
  const ctx = await buildContext(deps, { ...none, page: "albums", album: "a1" }, []);
  assert.deepEqual(ctx.project, { external_project_id: "a1", title: "Trip" });
  assert.equal(ctx.active_objects[0].kind, "album");
  assert.equal(ctx.active_objects[0].photo_count, 25);
  assert.equal(ctx.active_objects[0].photo_ids.length, 20);
  assert.equal(ctx.view.page, "albums");
  assert.equal(ctx.view.object_id, "a1");
});

test("a video key frame adds its video and the frame, without photo edits", async () => {
  const ctx = await buildContext(deps, { ...none, page: "videos", video: "v1", photo: { id: "f1", name: "trip.mp4", video_id: "v1", timestamp: "00:12" } }, []);
  assert.deepEqual(ctx.active_objects.map((o) => `${o.kind}:${o.object_id}`), ["video:v1", "photo:f1"]);
  assert.equal(ctx.active_objects[1].timestamp, "00:12");
  assert.equal(ctx.active_objects[1].rating, undefined);
  assert.equal(ctx.view.object_id, "f1");
});

test("unknown ids, creation forms and fetch errors yield no object and never throw", async () => {
  for (const open of [
    { ...none, photo: { id: "gone", name: "x" } },
    { ...none, album: "gone" },
    { ...none, album: "new" },
    { ...none, video: "gone" },
    none,
  ]) {
    const ctx = await buildContext(deps, open, []);
    assert.deepEqual(ctx.active_objects, [], JSON.stringify(open));
    assert.equal(ctx.project, undefined);
  }
  const broken = { getPhoto: () => { throw new Error("sync"); }, getEdits: async () => null, getAlbum: async () => null, getVideo: async () => null };
  assert.deepEqual((await buildContext(broken, { ...none, photo: { id: "p1", name: "x" } }, [])).active_objects, []);
});

test("an open edit form names its photo even when it is not the open one; creation forms add none", async () => {
  const ctx = await buildContext(deps, none, [
    { kind: "photo-edits", object_id: "p1", dirty: true, fields: { label: "Z" } },
    { kind: "album-new", object_id: null, dirty: true, fields: { name: "New" } },
  ]);
  assert.deepEqual(ctx.active_objects.map((o) => o.object_id), ["p1"]);
  assert.equal(ctx.view.editor.kind, "photo-edits");
  assert.equal(ctx.view.editors.length, 2);
  const creating = await buildContext(deps, none, [{ kind: "album-new", object_id: null, dirty: true, fields: { name: "New" } }]);
  assert.deepEqual(creating.active_objects, []);
  assert.deepEqual(creating.view.editor.fields, { name: "New" });
});

test("search state appears only on the search page", async () => {
  const search = { query: "beach", place: "Lisbon" };
  assert.deepEqual((await buildContext(deps, { ...none, page: "search", search }, [])).view.search, search);
  assert.equal((await buildContext(deps, { ...none, page: "library", search }, [])).view.search, undefined);
});

test("forms answer the context request", () => {
  const target = new EventTarget();
  target.addEventListener(CONTEXT_EVENT, (e) => e.detail.provide({ kind: "photo-edits", object_id: "p1", dirty: false, fields: {} }));
  target.addEventListener(CONTEXT_EVENT, (e) => e.detail.provide(null));
  assert.deepEqual(collectEditors(target).map((e) => e.kind), ["photo-edits"]);
});

test("registered views are readable and clear themselves only if still current", () => {
  setPage("albums");
  const off = registerOpen("album", "a1");
  assert.equal(openState().album, "a1");
  const off2 = registerOpen("album", "a2");
  off(); // the first one was replaced: must not wipe the second
  assert.equal(openState().album, "a2");
  off2();
  assert.equal(openState().album, null);
  assert.equal(openState().page, "albums");
});

test("turn end (event and callback) refreshes every mounted view once", async () => {
  const target = new EventTarget();
  installCopilot(deps, target);
  assert.equal(typeof target.hoardCopilot.context, "function");
  const existing = target.hoardCopilot;
  installCopilot(deps, target); // a second call leaves the first in place
  assert.equal(target.hoardCopilot, existing);
  let a = 0;
  let b = 0;
  const offA = onRefresh(() => { a += 1; });
  onRefresh(() => { b += 1; throw new Error("a broken view must not stop the others"); });
  target.dispatchEvent(new Event(TURN_END_EVENT));
  target.hoardCopilot.onTurnEnd();
  await new Promise((r) => setTimeout(r, 400));
  assert.deepEqual([a, b], [1, 1]);
  offA();
});

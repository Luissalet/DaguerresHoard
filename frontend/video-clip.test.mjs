import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { act, create } from "react-test-renderer";
import { createServer } from "vite";

test("shipping video view preserves later drafts and isolates pending exports across A to B", async () => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  globalThis.window = new EventTarget();
  const server = await createServer({ configFile: false, appType: "custom", optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true, hmr: false, watch: null }, ssr: { external: ["react", "react-dom", "lucide-react"] } });
  let view;
  try {
    const { default: VideosPage } = await server.ssrLoadModule("/src/pages/VideosPage.tsx");
    const { api } = await server.ssrLoadModule("/src/api.ts");
    const { dict } = await server.ssrLoadModule("/src/i18n.ts");
    const video = id => ({ id, name: `${id}.mp4`, path: `C:/fake/${id}.mp4`, size: 10000, duration: 4, duration_label: "00:04", frame_count: 0, frames: [] });
    api.listVideos = async () => ({ results: [video("A"), video("B")] });
    api.getVideo = async id => video(id);
    const pending = [], calls = [];
    api.exportVideoClip = (id, start_s, end_s) => { calls.push({ id, start_s, end_s }); return new Promise((resolve, reject) => pending.push({ resolve, reject })); };
    const receipt = (id, end = 3.25) => ({ id: `out-${id}`, video_id: id, source_name: `${id}.mp4`, requested: { start_s: 1.25, end_s: end, duration_s: end - 1.25 }, measured: { duration_s: end - 1.25, width: 160, height: 120 }, bytes: 9000, video_url: `/photos/api/exports/out-${id}/clip.mp4`, manifest_url: `/api/exports/out-${id}/manifest.json` });
    const inputs = () => view.root.findAllByType("input");
    const change = (index, value) => act(async () => inputs()[index].props.onChange({ target: { value } }));
    const submit = () => act(async () => { void view.root.findByType("form").props.onSubmit({ preventDefault() {} }); });
    const text = () => JSON.stringify(view.toJSON());
    const open = index => act(async () => { await view.root.findAllByProps({ className: "video-card" })[index].props.onClick(); });
    await act(async () => { view = create(React.createElement(VideosPage, { t: dict.en, platformIsWindows: true, status: null })); });
    await open(0); await change(0, "1.25"); await change(1, "3.25"); await submit();
    assert.deepEqual(calls[0], { id: "A", start_s: 1.25, end_s: 3.25 });
    await change(1, "3.75");
    await act(async () => pending.shift().resolve(receipt("A")));
    assert.equal(inputs()[1].props.value, "3.75");
    assert.match(text(), /out-A/);
    assert.equal(view.root.findAllByType("a").find(link => link.props.download.endsWith(".mp4")).props.href, "/photos/api/exports/out-A/clip.mp4");
    assert.match(text(), /3.25/);
    await submit();
    await act(async () => view.root.findAllByType("button").find(button => button.children.includes(dict.en.nav_videos)).props.onClick());
    await open(1); await change(0, "1.25"); await change(1, "3.25"); await submit();
    await act(async () => pending.shift().resolve(receipt("A", 3.75)));
    assert.match(text(), /Exporting/); assert.doesNotMatch(text(), /out-A/);
    await act(async () => pending.shift().reject(new Error("Own export failure")));
    assert.match(text(), /Own export failure/); assert.equal(inputs()[1].props.value, "3.25");
    await change(1, "2.5"); await submit();
    await act(async () => pending.shift().resolve(receipt("B", 2.5)));
    assert.deepEqual(calls.at(-1), { id: "B", start_s: 1.25, end_s: 2.5 });
    assert.match(text(), /out-B/); assert.doesNotMatch(text(), /Own export failure|out-A/);
    const snapshots = [];
    window.dispatchEvent(new CustomEvent("daguerre:context-request", { detail: { provide: value => snapshots.push(value) } }));
    const context = snapshots.find(value => value.kind === "video-clip-export");
    assert.equal(context.object_id, "B"); assert.equal(context.fields.export.requested.end_s, 2.5);
    // The host's detail read is also tied to the explicit choice. A slow A
    // must not reopen A after the user has already reached B's export form.
    await act(async () => view.root.findAllByType("button").find(button => button.children.includes(dict.en.nav_videos)).props.onClick());
    let finishA;
    api.getVideo = id => id === "A" ? new Promise(resolve => { finishA = resolve; }) : Promise.resolve(video(id));
    await act(async () => { void view.root.findAllByProps({ className: "video-card" })[0].props.onClick(); });
    await open(1);
    await act(async () => finishA(video("A")));
    assert.match(text(), /B\.mp4/); assert.doesNotMatch(text(), /A\.mp4/);
  } finally {
    if (view) await act(async () => view.unmount());
    await server.close(); delete globalThis.window; delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  }
});

import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { act, create } from "react-test-renderer";
import { createServer } from "vite";

async function setup(run) {
  const previousWindow = globalThis.window;
  globalThis.window = new EventTarget();
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const server = await createServer({ configFile: false, appType: "custom", server: { middlewareMode: true, hmr: false, watch: null }, ssr: { external: ["react", "react-dom", "lucide-react"] } });
  let rendered;
  try {
    const { default: SearchPage } = await server.ssrLoadModule("/src/pages/SearchPage.tsx");
    const { api } = await server.ssrLoadModule("/src/api.ts");
    const { dict } = await server.ssrLoadModule("/src/i18n.ts");
    const context = await server.ssrLoadModule("/src/copilot-context.ts");
    const pending = [];
    api.search = (query, filters, limit) => new Promise((resolve, reject) => pending.push({ query, filters, limit, resolve, reject }));
    await act(async () => { rendered = create(React.createElement(SearchPage, { t: dict.en, platformIsWindows: false, onOpenSettings() {} })); });
    const root = rendered.root;
    const field = name => root.findAllByType("label").find(label => label.findAllByType("span").some(span => span.children.includes(name))).findAll(node => ["input", "select"].includes(node.type))[0];
    const change = (name, value) => act(async () => field(name).props.onChange({ target: { value } }));
    const submit = () => act(async () => { void root.findByType("form").props.onSubmit({ preventDefault() {} }); });
    await run({ rendered, root, dict, pending, change, submit, field, context });
  } finally {
    if (rendered) await act(async () => rendered.unmount());
    await server.close();
    globalThis.window = previousWindow;
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  }
}
const photo = id => ({ id, path: `C:/Fixture/${id}.jpg`, width: 320, height: 480, size: 20000, taken_at: "2026-01-15T10:00:00" });
const response = (results, total = results.length) => ({ query: null, mode: "filtered_listing", results, returned: results.length, indexed_total: total, count: total, has_more: results.length < total, note_codes: ["filtered_listing"] });

test("filter-only search submits existing criteria and labels the native partial listing honestly", async () => setup(async ({ rendered, root, dict, pending, change, submit }) => {
  assert.equal(root.findByProps({ type: "submit" }).props.disabled, true);
  await submit(); assert.equal(pending.length, 0);
  await change(dict.en.filter_folder, "  Viaje QA  ");
  await change(dict.en.filter_camera, "Cam A");
  await change(dict.en.filter_orientation, "portrait");
  assert.equal(root.findByProps({ type: "submit" }).props.disabled, false);
  await submit();
  assert.deepEqual({ query: pending[0].query, filters: pending[0].filters, limit: pending[0].limit }, { query: "", filters: { folder: "Viaje QA", camera: "Cam A", orientation: "portrait" }, limit: 50 });
  await act(async () => pending[0].resolve(response(Array.from({ length: 50 }, (_, n) => photo(`match-${n}`)), 123)));
  const text = JSON.stringify(rendered.toJSON());
  assert.ok(text.includes(dict.en.filtered_count(50, 123)));
  assert.ok(text.includes(dict.en.filtered_listing_limit));
  assert.ok(text.includes(dict.en.filtered_listing_note));
  assert.equal(text.includes(dict.en.ranked_count(50, 123)), false);
  assert.equal(dict.es.filtered_count(1, 1), "1 mostrada de 1 foto");
}));

test("editing pending criteria discards old results and errors keep the new draft for retry", async () => setup(async ({ rendered, root, dict, pending, change, submit, field, context }) => {
  await change(dict.en.filter_folder, "Autor"); await submit();
  assert.equal(context.openState().search.folder, "Autor");
  await change(dict.en.filter_folder, "SDK");
  assert.equal(context.openState().search, null);
  assert.equal(context.collectEditors().find(editor => editor.kind === "search").fields.folder, "SDK");
  await submit();
  assert.equal(context.openState().search.folder, "SDK");
  await act(async () => pending[0].resolve(response([photo("Autor-old")])));
  assert.equal(root.findByProps({ "aria-busy": true }).props.hidden, true);
  assert.equal(JSON.stringify(rendered.toJSON()).includes("Autor-old.jpg"), false);
  await act(async () => pending[1].reject(new Error("503 fixture")));
  assert.equal(field(dict.en.filter_folder).props.value, "SDK");
  assert.ok(JSON.stringify(rendered.toJSON()).includes("503 fixture"));
  assert.equal(root.findByProps({ type: "submit" }).props.disabled, false);
  await submit();
  assert.equal(pending[2].filters.folder, "SDK");
  await act(async () => pending[2].resolve(response([])));
  assert.ok(JSON.stringify(rendered.toJSON()).includes(dict.en.filtered_count(0, 0)));
  assert.equal(field(dict.en.filter_folder).props.value, "SDK");
}));

import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { act, create } from "react-test-renderer";
import { createServer } from "vite";

test("Search keeps A/B mounted through loading, a filtered/empty list and restoring results", async () => {
  const previousWindow = globalThis.window;
  globalThis.window = new EventTarget();
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const server = await createServer({ configFile: false, appType: "custom", server: { middlewareMode: true, hmr: false, watch: null }, ssr: { external: ["react", "react-dom", "lucide-react"] } });
  let rendered;
  try {
    const { default: SearchPage } = await server.ssrLoadModule("/src/pages/SearchPage.tsx");
    const { default: PhotoSelection } = await server.ssrLoadModule("/src/components/PhotoSelection.tsx");
    const { api } = await server.ssrLoadModule("/src/api.ts");
    const { dict } = await server.ssrLoadModule("/src/i18n.ts");
    const t = dict.en;
    const photos = [
      { id: "red", path: "C:/QA/red/same.jpg", width: 320, height: 240, size: 100, taken_at: null },
      { id: "blue", path: "C:/QA/blue/same.jpg", width: 640, height: 480, size: 200, taken_at: null },
    ];
    const pending = [];
    api.search = (query, filters) => new Promise(resolve => pending.push({ query, filters, resolve }));
    api.getPhoto = async id => photos.find(photo => photo.id === id);
    const response = results => ({ results, returned: results.length, indexed_total: results.length, has_more: false, embedder: "fixture", note_codes: [], mode: "filtered_listing" });
    await act(async () => { rendered = create(React.createElement(SearchPage, { t, platformIsWindows: false, onOpenSettings() {} })); });
    const root = rendered.root;
    const submit = () => act(async () => { void root.findByType("form").props.onSubmit({ preventDefault() {} }); });
    const answer = results => act(async () => { pending.shift().resolve(response(results)); });
    const panel = () => root.findByProps({ "aria-label": t.compare_title });
    const sides = () => panel().findAllByProps({ className: "comparison-side" });
    const pair = () => panel().findAllByType("select").map(select => select.props.value);
    const folder = root.findAllByType("label").find(label => label.findAllByType("span").some(span => span.children.includes(t.filter_folder))).findByType("input");
    await act(async () => { root.findByProps({ placeholder: t.search_placeholder }).props.onChange({ target: { value: "red" } }); });
    await submit(); await answer(photos);
    await act(async () => { root.findAllByType("button").find(button => button.children.includes(t.compare_title)).props.onClick(); });
    await act(async () => { const selects = panel().findAllByType("select"); selects[0].props.onChange({ target: { value: "red" } }); selects[1].props.onChange({ target: { value: "blue" } }); });
    assert.deepEqual(pair(), ["red", "blue"]);
    await act(async () => { folder.props.onChange({ target: { value: "C:/QA/red" } }); });
    await submit();
    assert.equal(root.findByType(PhotoSelection).parent.props.hidden, true);
    assert.deepEqual(pair(), ["red", "blue"]);
    assert.equal(sides()[1].findAllByType("dd").length, 0);
    assert.equal(pending[0].filters.folder, "C:/QA/red");
    await answer([photos[0]]);
    assert.equal(root.findByType(PhotoSelection).parent.props.hidden, false);
    assert.deepEqual(pair(), ["red", "blue"]);
    assert.ok(sides()[1].findAllByType("p").some(p => p.children.includes(t.compare_not_visible)));
    assert.equal(sides()[1].findAllByType("dd").length, 0);
    await submit(); await answer([]);
    assert.deepEqual(pair(), ["red", "blue"]);
    assert.equal(sides()[0].findAllByType("dd").length, 0);
    await act(async () => { folder.props.onChange({ target: { value: "" } }); });
    await submit(); await answer(photos);
    assert.deepEqual(pair(), ["red", "blue"]);
    assert.equal(sides()[0].findAllByType("dd")[0].children.join(""), "320 × 240");
    assert.equal(sides()[1].findAllByType("dd")[0].children.join(""), "640 × 480");
  } finally {
    if (rendered) await act(async () => rendered.unmount());
    await server.close();
    globalThis.window = previousWindow;
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  }
});

import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { act, create } from "react-test-renderer";
import { createServer } from "vite";

test("album selection sends loaded IDs and retains later name, error draft and context identity", async () => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const server = await createServer({ configFile: false, appType: "custom", optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true, hmr: false, watch: null }, ssr: { external: ["react", "react-dom", "lucide-react"] } });
  let view;
  try {
    const { default: SelectionAlbum } = await server.ssrLoadModule("/src/components/SelectionAlbum.tsx");
    const { api } = await server.ssrLoadModule("/src/api.ts");
    const { dict } = await server.ssrLoadModule("/src/i18n.ts");
    assert.equal(dict.es.album_selection_result(1, 2), "1 foto incorporada ahora · 2 en el álbum");
    assert.equal(dict.es.album_selection_result(0, 2), "0 fotos incorporadas ahora · 2 en el álbum");
    const calls = [], pending = [];
    api.listAlbums = async () => [];
    api.albumAdd = (name, ids) => { calls.push({ name, ids }); return new Promise((resolve, reject) => pending.push({ resolve, reject })); };
    const photo = id => ({ id, path: `C:/fake/${id}.jpg`, thumbnail_url: `/fake/${id}` });
    const props = ids => ({ photos: ids.map(photo), t: dict.en });
    const input = () => view.root.findByType("input");
    const change = value => act(async () => input().props.onChange({ target: { value } }));
    const submit = () => act(async () => { void view.root.findByType("form").props.onSubmit({ preventDefault() {} }); });
    const receipt = (extra = {}) => ({ id: "album1", name: "Álbum ñ", created: false, added: 1, photo_count: 12, photos: [], unknown_ids: ["unknown"], has_more: true, ...extra });
    const text = () => JSON.stringify(view.toJSON());
    await act(async () => { view = create(React.createElement(SelectionAlbum, props(["A", "B"]))); });
    await change("Álbum ñ"); await submit();
    assert.deepEqual(calls[0], { name: "Álbum ñ", ids: ["A", "B"] });
    await act(async () => pending.shift().reject(new Error("Retry own failure")));
    assert.equal(input().props.value, "Álbum ñ"); assert.match(text(), /Retry own failure/);
    await submit(); await change("Later draft");
    await act(async () => pending.shift().resolve(receipt()));
    assert.equal(input().props.value, "Later draft");
    assert.match(text(), /1 newly added · 12 in the album/); assert.match(text(), /Existing album/); assert.match(text(), /unknown/);
    assert.equal(view.root.findAllByType("li").length, 2);
    await submit();
    await act(async () => view.update(React.createElement(SelectionAlbum, props(["C"]))));
    await act(async () => pending.shift().resolve(receipt({ name: "Stale album" })));
    assert.doesNotMatch(text(), /Stale album|12 in the album/); assert.equal(input().props.value, "Later draft");
    await submit(); await act(async () => pending.shift().resolve(receipt({ name: "New album", created: true, added: 1, photo_count: 1, unknown_ids: [] })));
    assert.deepEqual(calls.at(-1), { name: "Later draft", ids: ["C"] });
    assert.match(text(), /Album created/); assert.match(text(), /1 newly added · 1 in the album/);
  } finally { if (view) await act(async () => view.unmount()); await server.close(); delete globalThis.IS_REACT_ACT_ENVIRONMENT; }
});

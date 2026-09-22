#!/usr/bin/env python3
"""Walk the agent use cases (docs/USE_CASES.md) over real MCP stdio.

Spawns argus_hoard/mcp_server.py exactly as Faustus does (a subprocess
speaking MCP over stdin/stdout, ARGUS_URL pointing at a running app) and
plays the part of a small local model: it starts from list_tools, picks
tools by their descriptions, chains ids from one result into the next and
reacts to errors. It never imports the app.

Usage:
    python scripts/agent_walkthrough.py --url http://127.0.0.1:8814 \
        [--truth data-uxtest/photos/photos_index.json] [--root <Pictures>] \
        [--only uc2,uc4] [--transcript out.json]

--truth (written by scripts/make_uxtest_photos.py) maps each file to the
scene that was drawn in it, so every result line can show what the photo
really is and each scenario can be judged, not just run.

For every call it prints: the tool and arguments, the size of the text
result (characters and a rough token estimate), the number of images in
the result (a text-only model must not get any it did not ask for), and a
one-line digest. Checks that fail are printed as "CHECK FAIL" and counted;
the exit code is the number of failed checks (0 = every check passed).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

REPO = Path(__file__).resolve().parents[1]
SERVER = REPO / "argus_hoard" / "mcp_server.py"


def approx_tokens(text: str) -> int:
    # JSON with ids and paths tokenises at roughly 3 characters per token
    return max(1, len(text) // 3)


class Agent:
    def __init__(self, session: ClientSession, truth: dict[str, str], root: str | None):
        self.s = session
        self.truth = truth
        self.root = root
        self.failures: list[str] = []
        self.transcript: list[dict] = []
        self.tools: dict[str, dict] = {}

    # -- plumbing --------------------------------------------------------- #
    def scene(self, path: str | None) -> str:
        if not path or not self.root:
            return "?"
        rel = os.path.relpath(path, self.root).replace("\\", "/")
        return self.truth.get(rel, "copy" if "Copia movil" in rel else "?")

    def check(self, ok: bool, label: str) -> bool:
        print(f"    {'check ok  ' if ok else 'CHECK FAIL'} {label}")
        if not ok:
            self.failures.append(label)
        return ok

    async def call(self, tool: str, **args) -> tuple[dict | None, int, str | None]:
        """Returns (parsed JSON of the first text block, image count, error text)."""
        shown = json.dumps(args, ensure_ascii=False)
        if len(shown) > 160:
            shown = shown[:157] + "..."
        t0 = time.perf_counter()
        res = await self.s.call_tool(tool, args)
        ms = (time.perf_counter() - t0) * 1000
        texts = [c.text for c in res.content if c.type == "text"]
        images = [c for c in res.content if c.type == "image"]
        img_bytes = sum(len(c.data) * 3 // 4 for c in images)
        text = texts[0] if texts else ""
        entry = {"tool": tool, "args": args, "ms": round(ms), "chars": len(text),
                 "tokens": approx_tokens(text), "images": len(images), "image_bytes": img_bytes,
                 "error": text if res.isError else None}
        self.transcript.append(entry)
        img = f", {len(images)} image(s) {img_bytes // 1024} KB" if images else ""
        print(f"  -> {tool}({shown})  {ms:.0f} ms, {len(text)} chars ~{approx_tokens(text)} tok{img}")
        if res.isError:
            print(f"     error: {text[:300]}")
            return None, len(images), text
        try:
            return json.loads(text), len(images), None
        except ValueError:
            print(f"     (not JSON) {text[:200]}")
            return None, len(images), None

    def show_results(self, data: dict, k: int = 8) -> None:
        keys = [key for key in ("query", "count", "returned", "indexed_total", "has_more", "embedder") if key in data]
        print("     " + ", ".join(f"{key}={data[key]}" for key in keys))
        if data.get("note"):
            print(f"     note: {data['note'][:220]}")
        for r in data.get("results", [])[:k]:
            band = r.get("relevance") or r.get("band") or ""
            print(f"     #{r.get('n')} {r.get('score', ''):<7} {band:<7} {self.scene(r.get('path')):<18} "
                  f"{r.get('taken_at', '')[:10]} {r.get('place') or '-':<22} {Path(r.get('path', '')).name}")

    # -- scenarios -------------------------------------------------------- #
    async def discover(self) -> None:
        print("\n== list_tools: what a model sees before any call ==")
        listed = await self.s.list_tools()
        total = 0
        for t in listed.tools:
            desc = t.description or ""
            schema = json.dumps(t.inputSchema, separators=(",", ":"))
            total += approx_tokens(desc) + approx_tokens(schema)
            self.tools[t.name] = {"description": desc, "schema": t.inputSchema}
            first = desc.strip().splitlines()[0] if desc.strip() else "(no description)"
            print(f"  {t.name:<18} ~{approx_tokens(desc) + approx_tokens(schema):>4} tok  {first[:90]}")
        print(f"  total tool budget ~{total} tokens for {len(listed.tools)} tools")
        self.check(len(listed.tools) >= 9, "all nine tools are listed")
        for name in ("photos_search", "photos_similar"):
            props = self.tools.get(name, {}).get("schema", {}).get("properties", {})
            default = props.get("contact_sheet", {}).get("default")
            self.check(default is False,
                       f"{name}: contact_sheet defaults to false for text-only models (got {default!r})")
        show = self.tools.get("photos_show", {}).get("description", "").lower()
        self.check("only if you can see images" in show, "photos_show says 'only if you can see images'")

    async def uc1_status(self) -> dict | None:
        print("\n== UC1 (agent side): is anything indexed? ==")
        lib, imgs, _ = await self.call("photos_library")
        if lib:
            emb = lib.get("embedder", {})
            print(f"     photo_count={lib.get('photo_count')} roots={len(lib.get('roots', []))} "
                  f"embedder={emb.get('name')} semantic={emb.get('semantic')} indexing={lib.get('indexing')}")
            if lib.get("note"):
                print(f"     note: {lib['note'][:200]}")
            self.check(imgs == 0, "photos_library returns no image")
        return lib

    async def uc2_dog(self) -> None:
        print("\n== UC2: 'Faustus, do you still have the photo of the dog on the beach from last summer?' ==")
        print("  (model translates to English and puts the season in the filters; it passes no contact_sheet)")
        data, imgs, _ = await self.call("photos_search", query="dog on the beach",
                                        taken_after="2024-06-01", taken_before="2024-09-30")
        if data:
            self.show_results(data)
            self.check(imgs == 0, "default photos_search returns no image (text-only model safe)")
            top = [self.scene(r["path"]) for r in data["results"][:5]]
            self.check(sum("dog" in s for s in top) >= 3, f"at least 3 of the top 5 are dog photos (got {top})")
            self.check("count" not in data or "returned" in data,
                       "result does not carry a bare, ambiguous 'count' a model can quote as 'N matches'")
            rel = [r for r in data["results"] if "relevance" in r or "band" in r]
            self.check(bool(rel), "each result has a relevance band (strong/medium/weak)")
        print("  (the same model forgets to translate)")
        data, imgs, _ = await self.call("photos_search", query="perro en la playa", year=2024)
        if data:
            self.show_results(data, k=4)
            self.check(bool(data.get("note")) and "english" in json.dumps(data).lower(),
                       "an untranslated Spanish query gets a hint to translate it")
        print("  (the live report: 'orange sunsets' with no filter)")
        data, imgs, _ = await self.call("photos_search", query="orange sunsets")
        if data:
            self.show_results(data, k=5)
            self.check(imgs == 0, "no image by default for 'orange sunsets' either")
            self.check("count" not in data or data.get("count") == len(data.get("results", [])),
                       f"no count larger than what was returned (count={data.get('count')}, "
                       f"returned={len(data.get('results', []))})")

    async def uc3_duplicates(self) -> None:
        print("\n== UC3: 'Faustus, how much space do the repeated photos take?' ==")
        data, imgs, _ = await self.call("photos_duplicates")
        if data:
            print(f"     exact: total_groups={data.get('total_groups')} reclaimable={data.get('reclaimable_bytes_total')}")
            for g in data.get("groups", [])[:3]:
                print(f"     keeper {Path(g['photos'][0]['path']).parent.name}/{Path(g['photos'][0]['path']).name} "
                      f"+{len(g['photos']) - 1} copies, {g.get('reclaimable_bytes')} B")
            keepers = [g["photos"][0]["path"] for g in data.get("groups", [])]
            self.check(all("Copia movil" not in k for k in keepers), "exact keepers are the camera-roll originals, not the backup")
        data, imgs, _ = await self.call("photos_duplicates", kind="near")
        if data:
            print(f"     near: total_groups={data.get('total_groups')} reclaimable={data.get('reclaimable_bytes_total')} "
                  f"has_more={data.get('has_more')}")
            wa_keepers = 0
            burst_group = None
            for g in data.get("groups", []):
                if "WhatsApp" in g["photos"][0]["path"]:
                    wa_keepers += 1
                if sum("BURST" in p["path"] for p in g["photos"]) >= 6:
                    burst_group = g
            self.check(wa_keepers == 0, "no WhatsApp copy is suggested as the keeper")
            self.check(burst_group is not None, "the 12-frame burst shows up as one near-duplicate group")
            if burst_group:
                print(f"     burst group: {len(burst_group['photos'])} photos, max_distance={burst_group.get('max_distance')}")

    async def uc4_album(self) -> None:
        print("\n== UC4: 'Faustus, make an album \"Lisboa 2024\" with every photo of the July 2024 Lisbon trip' ==")
        ids: list[str] = []
        data, _, err = await self.call("photos_search", query="photo", place="Lisbon", year=2024, month=7, limit=50)
        if data:
            self.show_results(data, k=3)
            ids = [r["id"] for r in data["results"]]
            if data.get("has_more"):
                print("     has_more=true: the model looks for a way to get the next page")
                schema = self.tools["photos_search"]["schema"].get("properties", {})
                pager = next((p for p in ("offset", "page", "cursor") if p in schema), None)
                if self.check(pager is not None, "photos_search offers a way to page past 50 results"):
                    more, _, _ = await self.call("photos_search", query="photo", place="Lisbon", year=2024, month=7,
                                                 limit=50, **{pager: 50 if pager == "offset" else 2})
                    ids += [r["id"] for r in (more or {}).get("results", [])]
                else:
                    await self.call("photos_search", query="photo", place="Lisbon", year=2024, month=7, limit=100)
        truth_trip = sum(1 for rel, s in self.truth.items() if rel.startswith("Camera Roll/2024/07/"))
        if ids:
            album, _, _ = await self.call("photos_album", name="Lisboa 2024", photo_ids=ids)
            if album:
                print(f"     album photo_count={album.get('photo_count')} added={album.get('added')}")
                if truth_trip:
                    self.check(album.get("photo_count", 0) >= truth_trip,
                               f"album holds the whole trip ({album.get('photo_count')} of {truth_trip})")

    async def uc5_portrait(self) -> None:
        print("\n== UC5: 'Faustus, find a vertical portrait with good resolution for my CV' ==")
        data, imgs, _ = await self.call("photos_search", query="portrait photo of a person",
                                        orientation="portrait", min_megapixels=2, limit=5)
        if not data or not data.get("results"):
            return
        self.show_results(data, k=5)
        best = data["results"][0]
        self.check(self.scene(best["path"]) == "portrait", f"top result is a portrait (got {self.scene(best['path'])})")
        info, _, _ = await self.call("photos_describe", photo_id=best["id"])
        if info:
            print(f"     path={info.get('path')} {info.get('width')}x{info.get('height')} camera={info.get('model')}")
            self.check(Path(info.get("path", "")).is_absolute(), "describe gives an absolute path another tool can copy")
            self.check(info.get("height", 0) > info.get("width", 0), "it really is vertical")
        print("  (Faustus's own file tool would now copy that path; Argus itself never copies)")

    async def uc6_fanfilm(self) -> None:
        print("\n== UC6: 'Faustus, put the clapperboard and green-screen shots from the March shoot in \"Rodaje La Estacion\"' ==")
        picked: list[str] = []
        for q in ("film clapperboard", "green screen studio"):
            data, imgs, _ = await self.call("photos_search", query=q, taken_after="2025-03-01",
                                            taken_before="2025-03-31", limit=10)
            if data:
                self.show_results(data, k=6)
                want = "clapper" if "clapper" in q else "greenscreen"
                strong = [r for r in data["results"] if (r.get("relevance") or r.get("band")) in ("strong", "medium")]
                chosen = strong or data["results"][:5]
                hits = [self.scene(r["path"]) for r in chosen]
                self.check(sum(h == want for h in hits) >= max(1, len(hits) // 2),
                           f"'{q}': the picks a text-only model would take are mostly {want} ({hits})")
                picked += [r["id"] for r in chosen]
        if picked:
            album, _, _ = await self.call("photos_album", name="Rodaje La Estacion", photo_ids=picked)
            if album:
                print(f"     album photo_count={album.get('photo_count')}")
        print("  (then Scheherazade's own tools would record the take count; out of scope for this app)")

    async def uc7_on_this_day(self) -> None:
        print("\n== UC7: 'Faustus, what photos did I take on this day in other years?' ==")
        data, imgs, _ = await self.call("photos_timeline")
        if not data:
            return
        otd = data.get("on_this_day", [])
        print(f"     years={data.get('years')} on_this_day_count={data.get('on_this_day_count')}")
        self.check(imgs == 0, "timeline returns no image")
        self.check(bool(otd), "on_this_day has photos (the data plants three on 22 September)")
        for item in otd[:3]:
            info, _, _ = await self.call("photos_describe", photo_id=item["id"])
            if info:
                print(f"     {info.get('taken_at')} {info.get('place') or info.get('city')} {self.scene(info.get('path'))}")

    async def errors(self) -> None:
        print("\n== Errors a small model makes: are they actionable? ==")
        cases = [
            ("photos_search", {"query": "beach", "month": 13}, "month"),
            ("photos_describe", {"photo_id": "IMG_20240714_183201"}, "photos_search"),
            ("photos_similar", {}, "photo_id"),
            ("photos_add_folder", {"path": "Pictures"}, "absolute"),
            ("photos_add_folder", {"path": str(Path(self.root or REPO).parent / "NoSuchFolder")}, "exist"),
            ("photos_album", {"name": "", "photo_ids": []}, "name"),
        ]
        if self.root:
            # Explorer's "Copy as path" wraps the path in quotes; accepting it is fine too
            cases.append(("photos_add_folder", {"path": f'"{self.root}"'}, "quote"))
        for tool, args, must in cases:
            data, _, err = await self.call(tool, **args)
            text = (err or json.dumps(data or {})).lower()
            ok = must.lower() in text or (must == "quote" and err is None)
            self.check(ok, f"{tool}({json.dumps(args, ensure_ascii=False)[:60]}) is accepted or says '{must}'")

    async def show_images(self, ids: list[str]) -> None:
        print("\n== photos_show: the one tool whose job is images ==")
        data, imgs, _ = await self.call("photos_show", ids=ids[:2], size=384)
        self.check(imgs == len(ids[:2]), "photos_show returns one image per id")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8814")
    ap.add_argument("--truth", type=Path)
    ap.add_argument("--root", help="the indexed Pictures folder (to read --truth paths)")
    ap.add_argument("--only", default="", help="comma-separated: discover,uc1,uc2,uc3,uc4,uc5,uc6,uc7,errors,show")
    ap.add_argument("--transcript", type=Path)
    args = ap.parse_args()
    truth = {}
    if args.truth and args.truth.exists():
        truth = {e["path"]: e["scene"] for e in json.loads(args.truth.read_text(encoding="utf-8"))}
    only = {s for s in args.only.split(",") if s}
    env = {**os.environ, "ARGUS_URL": args.url}
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"server: {init.serverInfo.name}; instructions: {len(init.instructions or '')} chars")
            agent = Agent(session, truth, args.root)
            steps = [("discover", agent.discover), ("uc1", agent.uc1_status), ("uc2", agent.uc2_dog),
                     ("uc3", agent.uc3_duplicates), ("uc4", agent.uc4_album), ("uc5", agent.uc5_portrait),
                     ("uc6", agent.uc6_fanfilm), ("uc7", agent.uc7_on_this_day), ("errors", agent.errors)]
            for name, fn in steps:
                if not only or name in only:
                    await fn()
            if not only or "show" in only:
                data, _, _ = await agent.call("photos_search", query="dog on the beach", limit=2)
                if data and data.get("results"):
                    await agent.show_images([r["id"] for r in data["results"]])
    calls = agent.transcript
    print(f"\n== summary: {len(calls)} calls, ~{sum(c['tokens'] for c in calls)} text tokens, "
          f"{sum(c['images'] for c in calls)} images, {len(agent.failures)} failed checks ==")
    for f in agent.failures:
        print(f"  FAIL {f}")
    if args.transcript:
        args.transcript.write_text(json.dumps(calls, indent=1, ensure_ascii=False), encoding="utf-8")
    return len(agent.failures)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

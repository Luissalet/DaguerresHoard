#!/usr/bin/env python3
"""Capture real screenshots of the running --demo app for the READMEs.

Usage: start the app with `python -m argus_hoard --demo --no-browser --port <p>`,
then run `python scripts/screenshots.py --port <p> [--out docs/media] [--lang en]`.
Requires the `playwright` package (not a project dependency) and a cached
Chromium (PLAYWRIGHT_BROWSERS_PATH). Output: 1440x900 PNGs, each under
400 KB (palette-quantised with Pillow when a plain PNG is larger).
"""
from __future__ import annotations

import argparse
import io
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
MAX_BYTES = 400_000


def save_png(raw: bytes, path: Path) -> None:
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    for colors in (None, 256, 192, 128):
        buf = io.BytesIO()
        out = img if colors is None else img.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        out.save(buf, format="PNG", optimize=True)
        if buf.tell() <= MAX_BYTES:
            break
    path.write_bytes(buf.getvalue())
    print(f"{path.name}: {path.stat().st_size // 1024} KB")


def nav(page, label: str) -> None:
    page.locator(".sidebar-item", has_text=label).first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8814)
    parser.add_argument("--out", type=Path, default=REPO / "docs" / "media")
    parser.add_argument("--lang", choices=["en", "es"], default="en")
    parser.add_argument("--theme", choices=["light", "dark"], default="light")
    parser.add_argument("--query", default="sunset over the sea")
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"
    args.out.mkdir(parents=True, exist_ok=True)
    labels = {
        "en": ["Search", "Duplicates", "Near duplicates", "Timeline", "Places", "Settings"],
        "es": ["Buscar", "Duplicados", "Duplicados aproximados", "Cronología", "Lugares", "Ajustes"],
    }[args.lang]

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1,
                                      locale="es-ES" if args.lang == "es" else "en-US")
        context.add_init_script(
            f"localStorage.setItem('argus-lang', '{args.lang}'); localStorage.setItem('argus-theme', '{args.theme}');"
        )
        page = context.new_page()

        page.goto(f"{base}/", wait_until="networkidle")
        page.wait_for_timeout(900)
        save_png(page.screenshot(), args.out / "library.png")

        nav(page, labels[0])
        page.locator(".search-input-wrap input").fill(args.query)
        page.locator("form.search-bar button[type=submit]").click()
        page.wait_for_selector(".grid .thumb")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(700)
        save_png(page.screenshot(), args.out / "search.png")

        page.locator(".grid .thumb").first.click()
        page.wait_for_selector(".lightbox-side .similar-strip")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(900)
        save_png(page.screenshot(), args.out / "lightbox.png")
        page.keyboard.press("Escape")

        nav(page, labels[1])
        page.locator(".segmented button", has_text=labels[2]).click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(700)
        save_png(page.screenshot(), args.out / "duplicates.png")

        nav(page, labels[3])
        save_png(page.screenshot(), args.out / "timeline.png")

        nav(page, labels[4])
        save_png(page.screenshot(), args.out / "places.png")

        nav(page, labels[5])
        save_png(page.screenshot(), args.out / "settings.png")

        browser.close()


if __name__ == "__main__":
    main()

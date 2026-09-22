#!/usr/bin/env python3
"""Capture a handful of real screenshots of the running --demo app.

Usage: start the app with `python -m argus_hoard --demo --no-browser --port <p>`,
then run this script with `python3 scripts/screenshots.py --port <p>`.
Requires the system `playwright` package (not a project dependency) with
PLAYWRIGHT_BROWSERS_PATH pointing at a cached chromium build.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "media"


def shoot(page, path: Path, max_bytes: int = 400_000) -> None:
    page.screenshot(path=str(path))
    if path.stat().st_size <= max_bytes:
        return
    from PIL import Image

    img = Image.open(path).convert("RGB")
    quality = 85
    while quality >= 40:
        jpg_path = path.with_suffix(".jpg")
        img.save(jpg_path, format="JPEG", quality=quality, optimize=True)
        if jpg_path.stat().st_size <= max_bytes:
            path.unlink()
            jpg_path.rename(path.with_suffix(".png"))
            return
        quality -= 10


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18841)
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)

        page.goto(f"{base}/", wait_until="networkidle")
        page.wait_for_timeout(600)
        shoot(page, OUT_DIR / "library.png")

        page.get_by_text("Search", exact=True).click()
        page.wait_for_timeout(200)
        page.locator("input.input").first.fill("sunset over the sea")
        page.get_by_text("Search", exact=True).nth(1).click() if False else None
        page.locator("button[type=submit]").click()
        page.wait_for_timeout(900)
        shoot(page, OUT_DIR / "search.png")

        page.get_by_text("Duplicates", exact=True).click()
        page.wait_for_timeout(700)
        shoot(page, OUT_DIR / "duplicates.png")

        page.get_by_text("Timeline", exact=True).click()
        page.wait_for_timeout(500)
        shoot(page, OUT_DIR / "timeline.png")

        page.get_by_text("Places", exact=True).click()
        page.wait_for_timeout(500)
        shoot(page, OUT_DIR / "places.png")

        browser.close()

    print("Saved screenshots to", OUT_DIR)


if __name__ == "__main__":
    main()

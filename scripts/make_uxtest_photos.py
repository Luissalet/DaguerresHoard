#!/usr/bin/env python3
"""Build a realistic, fully synthetic photo folder for usability testing.

Usage: python scripts/make_uxtest_photos.py [--out data-uxtest/photos] [--seed 11]

Everything is drawn with Pillow (no real photos, no personal data), but the
folder looks like a real phone + camera library: a camera roll split by
year/month, two trips with GPS and the local time-zone offset (Lisbon,
Tokyo), a beach day with a 12-shot burst of near-identical frames, a
WhatsApp folder of downscaled copies with the EXIF stripped, a backup
folder of byte-identical copies, screenshots (PNG), old scans (TIFF, no
EXIF), a short-film shoot, a beach with GPS far from any bundled city, and a
"misc" folder with the awkward files real folders contain (truncated JPEG,
empty file, tiny icon, text file, HEIC, WebP, GIF, an unsupported RAW).

Idempotent: an existing output folder is removed and rebuilt. Prints a
summary of what it created (counts per folder) as JSON on the last line.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import random
import shutil
from pathlib import Path

import numpy as np
from PIL import ExifTags, Image, ImageDraw, ImageFilter, ImageFont
from PIL.TiffImagePlugin import IFDRational

REPO = Path(__file__).resolve().parents[1]
_TAG = {v: k for k, v in ExifTags.TAGS.items()}
_GPS = {v: k for k, v in ExifTags.GPSTAGS.items()}
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
HAND = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Fictional camera identities (make, model, lens, focal, f-number*10)
PHONE = ("Nimbus", "Nimbus 8 Pro", None, 6.9, 18)
CAMERA = ("Orrery Optics", "OX-7 Mirrorless", "OX 24-70mm F2.8", 35.0, 28)
OLDPHONE = ("Nimbus", "Nimbus 5", None, 4.2, 22)

PLACES = {
    "lisbon": (38.7139, -9.1334),     # Alfama
    "belem": (38.6916, -9.2160),
    "tokyo": (35.6586, 139.7454),
    "kyoto": (35.0116, 135.7681),     # not in the bundled 10-city table
    "madrid": (40.4153, -3.6844),     # Retiro
    "cadiz": (36.5271, -6.2886),      # beach far from every bundled city
    "home": (40.4381, -3.6795),
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(HAND if bold else FONT, size)


def _dms(v: float) -> tuple:
    v = abs(v)
    d = int(v)
    m = int((v - d) * 60)
    s = round(((v - d) * 60 - m) * 60, 3)
    return (IFDRational(d, 1), IFDRational(m, 1), IFDRational(int(s * 1000), 1000))


def exif_bytes(taken: dt.datetime, cam=PHONE, gps: tuple[float, float] | None = None,
               offset: str = "+02:00", orientation: int | None = None) -> bytes:
    make, model, lens, focal, fnum = cam
    ex = Image.Exif()
    ex[_TAG["Make"]] = make
    ex[_TAG["Model"]] = model
    ex[_TAG["DateTime"]] = taken.strftime("%Y:%m:%d %H:%M:%S")
    if orientation:
        ex[_TAG["Orientation"]] = orientation
    sub = {
        _TAG["DateTimeOriginal"]: taken.strftime("%Y:%m:%d %H:%M:%S"),
        _TAG["OffsetTimeOriginal"]: offset,
        _TAG["FNumber"]: IFDRational(fnum, 10),
        _TAG["ExposureTime"]: IFDRational(1, random.choice([60, 125, 250, 500, 1000])),
        _TAG["ISOSpeedRatings"]: random.choice([50, 100, 200, 400, 800, 1600]),
        _TAG["FocalLength"]: IFDRational(int(focal * 10), 10),
    }
    if lens:
        sub[_TAG["LensModel"]] = lens
    ex[0x8769] = sub
    if gps:
        lat, lon = gps
        ex[_TAG["GPSInfo"]] = {
            _GPS["GPSLatitudeRef"]: "N" if lat >= 0 else "S", _GPS["GPSLatitude"]: _dms(lat),
            _GPS["GPSLongitudeRef"]: "E" if lon >= 0 else "W", _GPS["GPSLongitude"]: _dms(lon),
        }
    return ex.tobytes()


def jitter(p: tuple[float, float], rng: random.Random, km: float = 1.5) -> tuple[float, float]:
    d = km / 111.0
    return (p[0] + rng.uniform(-d, d), p[1] + rng.uniform(-d, d))


def grain(img: Image.Image, seed: int, amount: int = 7) -> Image.Image:
    arr = np.asarray(img, dtype=np.int16)
    noise = np.random.default_rng(seed).integers(-amount, amount + 1, size=arr.shape)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype("uint8"), "RGB")


def vgrad(d: ImageDraw.ImageDraw, box, top, bottom) -> None:
    x0, y0, x1, y1 = box
    h = max(1, y1 - y0)
    for y in range(y0, y1):
        t = (y - y0) / h
        d.line([(x0, y), (x1, y)], fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))


# ---------------------------------------------------------------- scenes -- #
# Each scene draws on a W x H canvas; rng controls composition so photos of
# the same kind are not accidental near-duplicates of each other.

def s_sunset(d, W, H, rng):
    hz = int(H * rng.uniform(0.55, 0.72))
    vgrad(d, (0, 0, W, hz), (rng.randint(60, 110), 40, rng.randint(90, 130)), (255, rng.randint(120, 170), 50))
    r = int(W * rng.uniform(0.05, 0.09))
    cx = int(W * rng.uniform(0.25, 0.75))
    d.ellipse([cx - r, hz - r * 1.3, cx + r, hz + r * 0.7], fill=(255, 215, 120))
    vgrad(d, (0, hz, W, H), (120, 60, 70), (25, 20, 50))
    for k in range(14):  # reflection
        y = hz + 8 + k * (H - hz) // 16
        w = int(r * (1.6 - k * 0.08))
        d.line([(cx - w, y), (cx + w, y)], fill=(255, 170, 90), width=3)


def s_beach(d, W, H, rng, dog=False, dx=0, dy=0):
    vgrad(d, (0, 0, W, int(H * 0.45)), (110, 170, 235), (190, 220, 245))
    vgrad(d, (0, int(H * 0.45), W, int(H * 0.6)), (30, 110, 170), (70, 160, 190))
    vgrad(d, (0, int(H * 0.6), W, H), (235, 215, 170), (215, 190, 140))
    for k in range(4):
        y = int(H * (0.58 + k * 0.012))
        d.line([(0, y), (W, y)], fill=(245, 250, 250), width=2)
    if rng.random() < 0.5:  # umbrella
        ux = int(W * rng.uniform(0.1, 0.9))
        d.line([(ux, int(H * 0.62)), (ux, int(H * 0.85))], fill=(90, 70, 50), width=6)
        d.pieslice([ux - 110, int(H * 0.55), ux + 110, int(H * 0.69)], 180, 360, fill=rng.choice([(220, 40, 40), (250, 200, 40), (40, 120, 220)]))
    if dog:
        x, y = int(W * 0.42) + dx, int(H * 0.72) + dy
        body = (150, 95, 45)
        d.ellipse([x - 120, y - 50, x + 120, y + 50], fill=body)
        for lx in (-90, -50, 50, 90):
            d.rectangle([x + lx - 12, y + 30, x + lx + 12, y + 120], fill=body)
        d.ellipse([x + 90, y - 120, x + 190, y - 20], fill=body)          # head
        d.ellipse([x + 160, y - 80, x + 225, y - 40], fill=(135, 85, 40))  # snout
        d.ellipse([x + 210, y - 72, x + 228, y - 56], fill=(20, 20, 20))   # nose
        d.polygon([(x + 95, y - 105), (x + 70, y - 30), (x + 115, y - 60)], fill=(110, 65, 30))  # ear
        d.ellipse([x + 150, y - 100, x + 164, y - 86], fill=(15, 15, 15))  # eye
        d.line([(x - 115, y - 20), (x - 190, y - 90)], fill=body, width=16)  # tail
        d.ellipse([x + 200, y + 60, x + 250, y + 110], fill=(230, 230, 60))  # ball


def s_city_night(d, W, H, rng):
    vgrad(d, (0, 0, W, H), (10, 12, 40), (30, 25, 60))
    d.ellipse([int(W * 0.8), 60, int(W * 0.8) + 70, 130], fill=(240, 240, 210))
    x = 0
    while x < W:
        bw, bh = rng.randint(80, 200), rng.randint(int(H * 0.3), int(H * 0.8))
        d.rectangle([x, H - bh, x + bw, H], fill=(20, 20, 30))
        for wy in range(H - bh + 15, H - 10, 28):
            for wx in range(x + 10, x + bw - 15, 22):
                if rng.random() < 0.55:
                    d.rectangle([wx, wy, wx + 10, wy + 14], fill=(255, 210, 110))
        x += bw + rng.randint(2, 12)


def s_mountain(d, W, H, rng):
    vgrad(d, (0, 0, W, H), (100, 160, 230), (220, 235, 250))
    for _ in range(4):
        cx, h = rng.randint(0, W), rng.randint(int(H * 0.4), int(H * 0.7))
        base = H
        w = rng.randint(int(W * 0.3), int(W * 0.6))
        d.polygon([(cx - w // 2, base), (cx, base - h), (cx + w // 2, base)], fill=(110, 115, 130))
        d.polygon([(cx - w // 9, base - h + h // 4.5), (cx, base - h), (cx + w // 9, base - h + h // 4.5)], fill=(250, 250, 255))
    d.rectangle([0, int(H * 0.9), W, H], fill=(240, 245, 250))


def s_forest(d, W, H, rng):
    vgrad(d, (0, 0, W, H), (150, 190, 160), (40, 80, 45))
    for _ in range(40):
        x, y, h = rng.randint(0, W), rng.randint(int(H * 0.2), H), rng.randint(90, 260)
        d.rectangle([x - 6, y + h - 20, x + 6, y + h + 30], fill=(80, 55, 30))
        d.polygon([(x, y), (x - 45, y + h), (x + 45, y + h)], fill=(20, 90 + rng.randint(-15, 25), 35))


def s_whiteboard(d, W, H, rng):
    d.rectangle([0, 0, W, H], fill=(200, 195, 185))
    d.rectangle([40, 40, W - 40, H - 60], fill=(250, 250, 246), outline=(160, 160, 160), width=8)
    lines = rng.sample(["Sprint 14 retro", "- flaky CI on Windows", "- vector store grows?",
                        "ACTION: pin deps", "Q3 roadmap", "MCP tools -> docs", "p95 latency 120ms",
                        "ship Friday?", "TODO: onboarding", "risks: model size"], 6)
    colors = [(30, 60, 170), (190, 30, 30), (30, 120, 60), (40, 40, 40)]
    y = 80
    for ln in lines:
        d.text((90 + rng.randint(0, 40), y), ln, fill=rng.choice(colors), font=font(int(H * 0.055), True))
        y += int(H * 0.11)
    d.rectangle([int(W * 0.62), int(H * 0.2), int(W * 0.9), int(H * 0.5)], outline=(190, 30, 30), width=6)
    d.line([(int(W * 0.55), int(H * 0.35)), (int(W * 0.62), int(H * 0.35))], fill=(190, 30, 30), width=6)


def s_receipt(d, W, H, rng):
    d.rectangle([0, 0, W, H], fill=(95, 70, 50))
    x0, x1 = int(W * 0.33), int(W * 0.67)
    d.rectangle([x0, 30, x1, H - 30], fill=(248, 246, 238))
    f = font(int(H * 0.028))
    y = 60
    d.text((x0 + 30, y), "CAFETERIA LA PLAZA", fill=(20, 20, 20), font=font(int(H * 0.032), True))
    y += 60
    total = 0.0
    for item in rng.sample(["Cafe con leche", "Tostada tomate", "Zumo naranja", "Croissant", "Agua 50cl", "Menu del dia"], 4):
        p = rng.randint(120, 1450) / 100
        total += p
        d.text((x0 + 30, y), f"{item:<18}{p:>6.2f}".replace(".", ","), fill=(30, 30, 30), font=f)
        y += 42
    d.text((x0 + 30, y + 30), f"TOTAL EUR {total:.2f}".replace(".", ","), fill=(10, 10, 10), font=font(int(H * 0.034), True))


def s_food(d, W, H, rng):
    d.rectangle([0, 0, W, H], fill=(150, 105, 65))
    for k in range(0, H, 40):
        d.line([(0, k), (W, k + 20)], fill=(135, 95, 60), width=3)
    cx, cy, r = W // 2 + rng.randint(-80, 80), H // 2, int(H * 0.38)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(245, 245, 245))
    pr = int(r * 0.8)
    d.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=(230, 170, 70))  # pizza
    d.ellipse([cx - pr + 18, cy - pr + 18, cx + pr - 18, cy + pr - 18], fill=(200, 50, 35))
    for _ in range(14):
        a, rr = rng.uniform(0, 6.28), rng.uniform(0, pr * 0.7)
        px, py = cx + rr * math.cos(a), cy + rr * math.sin(a)
        d.ellipse([px - 18, py - 18, px + 18, py + 18], fill=rng.choice([(250, 240, 200), (60, 120, 40), (150, 30, 30)]))


def s_cake(d, W, H, rng):
    vgrad(d, (0, 0, W, H), (60, 40, 50), (30, 20, 25))
    cx, top = W // 2, int(H * 0.45)
    d.rectangle([cx - 220, top, cx + 220, top + 200], fill=(250, 220, 230))
    d.rectangle([cx - 220, top, cx + 220, top + 30], fill=(240, 120, 160))
    for k in range(rng.randint(4, 9)):
        x = cx - 180 + k * 45
        d.rectangle([x, top - 70, x + 10, top], fill=rng.choice([(80, 150, 240), (250, 200, 60), (120, 220, 120)]))
        d.ellipse([x - 6, top - 105, x + 16, top - 68], fill=(255, 200, 60))
    d.ellipse([cx - 300, top + 180, cx + 300, top + 250], fill=(230, 230, 230))


def s_concert(d, W, H, rng):
    d.rectangle([0, 0, W, H], fill=(8, 6, 14))
    for _ in range(5):
        x = rng.randint(0, W)
        col = rng.choice([(200, 40, 200), (40, 120, 255), (255, 60, 60), (60, 255, 180)])
        d.polygon([(x, 0), (x - 160, int(H * 0.75)), (x + 160, int(H * 0.75))], fill=tuple(c // 3 for c in col))
    d.rectangle([0, int(H * 0.62), W, int(H * 0.68)], fill=(40, 40, 50))
    for k in range(3):
        px = int(W * (0.3 + k * 0.2))
        d.ellipse([px - 18, int(H * 0.45), px + 18, int(H * 0.5)], fill=(0, 0, 0))
        d.rectangle([px - 22, int(H * 0.5), px + 22, int(H * 0.62)], fill=(0, 0, 0))
    for x in range(0, W, 26):  # crowd heads
        hy = int(H * 0.82) + rng.randint(-20, 20)
        d.ellipse([x, hy, x + 30, hy + 34], fill=(0, 0, 0))
        d.rectangle([x - 4, hy + 30, x + 34, H], fill=(0, 0, 0))


def s_clapper(d, W, H, rng):
    vgrad(d, (0, 0, W, H), (40, 40, 45), (15, 15, 18))
    x0, y0 = int(W * 0.25), int(H * 0.3)
    d.rectangle([x0, y0, x0 + int(W * 0.5), y0 + int(H * 0.45)], fill=(20, 20, 20), outline=(230, 230, 230), width=4)
    for k in range(8):  # stripes
        sx = x0 + k * int(W * 0.0625)
        d.polygon([(sx, y0 - 60), (sx + 40, y0 - 60), (sx + 70, y0), (sx + 30, y0)], fill=(240, 240, 240) if k % 2 else (20, 20, 20))
    f = font(int(H * 0.04), True)
    d.text((x0 + 30, y0 + 30), "LA ESTACION", fill=(240, 240, 240), font=f)
    d.text((x0 + 30, y0 + 100), f"ESCENA {rng.randint(1, 40)}   TOMA {rng.randint(1, 9)}", fill=(240, 240, 240), font=f)
    d.text((x0 + 30, y0 + 170), "DIR: short film", fill=(240, 240, 240), font=f)


def s_greenscreen(d, W, H, rng):
    d.rectangle([0, 0, W, H], fill=(40, 190, 70))
    d.rectangle([0, int(H * 0.85), W, H], fill=(35, 160, 60))
    cx = int(W * rng.uniform(0.35, 0.65))
    d.ellipse([cx - 45, int(H * 0.25), cx + 45, int(H * 0.37)], fill=(220, 180, 150))
    d.polygon([(cx - 90, int(H * 0.37)), (cx + 90, int(H * 0.37)), (cx + 130, int(H * 0.85)), (cx - 130, int(H * 0.85))], fill=(90, 20, 20))  # cape
    d.line([(cx + 80, int(H * 0.45)), (cx + 200, int(H * 0.2))], fill=(200, 200, 210), width=10)  # sword
    for k in range(3):
        d.rectangle([40 + k * 120, 30, 70 + k * 120, 60], fill=(250, 250, 250))  # tracking marks


def s_portrait(d, W, H, rng):
    vgrad(d, (0, 0, W, H), (rng.randint(150, 210), 200, 220), (90, 110, 130))
    cx, cy = W // 2 + rng.randint(-40, 40), int(H * 0.4)
    skin = rng.choice([(235, 200, 170), (200, 150, 110), (140, 95, 65)])
    d.ellipse([cx - int(W * 0.42), int(H * 0.68), cx + int(W * 0.42), int(H * 1.3)], fill=rng.choice([(40, 60, 120), (150, 40, 40), (40, 40, 40)]))
    d.rectangle([cx - 40, int(H * 0.52), cx + 40, int(H * 0.72)], fill=skin)
    d.ellipse([cx - 130, cy - 170, cx + 130, cy + 170], fill=skin)
    d.pieslice([cx - 145, cy - 195, cx + 145, cy + 60], 180, 360, fill=rng.choice([(40, 25, 15), (120, 80, 30), (20, 20, 20)]))
    for ex in (-55, 55):
        d.ellipse([cx + ex - 18, cy - 20, cx + ex + 18, cy + 5], fill=(255, 255, 255))
        d.ellipse([cx + ex - 8, cy - 15, cx + ex + 8, cy + 2], fill=(40, 30, 20))
    d.arc([cx - 60, cy + 40, cx + 60, cy + 110], 20, 160, fill=(150, 60, 60), width=6)


def s_cat(d, W, H, rng):
    d.rectangle([0, 0, W, H], fill=rng.choice([(180, 160, 140), (90, 110, 150), (200, 200, 190)]))
    fur = rng.choice([(230, 140, 50), (120, 120, 120), (40, 40, 40)])
    cx, cy = W // 2, int(H * 0.55)
    d.ellipse([cx - 220, cy - 180, cx + 220, cy + 180], fill=fur)
    d.polygon([(cx - 200, cy - 90), (cx - 160, cy - 300), (cx - 60, cy - 170)], fill=fur)
    d.polygon([(cx + 200, cy - 90), (cx + 160, cy - 300), (cx + 60, cy - 170)], fill=fur)
    for ex in (-90, 90):
        d.ellipse([cx + ex - 40, cy - 60, cx + ex + 40, cy + 10], fill=(120, 200, 80))
        d.ellipse([cx + ex - 8, cy - 55, cx + ex + 8, cy + 5], fill=(10, 10, 10))
    d.polygon([(cx - 20, cy + 40), (cx + 20, cy + 40), (cx, cy + 65)], fill=(230, 120, 140))
    for s in (-1, 1):
        for k in range(3):
            d.line([(cx + s * 40, cy + 60 + k * 12), (cx + s * 260, cy + 30 + k * 30)], fill=(250, 250, 250), width=3)


def s_torii(d, W, H, rng):
    vgrad(d, (0, 0, W, H), (170, 200, 230), (230, 225, 210))
    d.rectangle([0, int(H * 0.8), W, H], fill=(150, 140, 120))
    red = (200, 40, 30)
    cx = W // 2 + rng.randint(-100, 100)
    d.rectangle([cx - 250, int(H * 0.3), cx - 210, int(H * 0.82)], fill=red)
    d.rectangle([cx + 210, int(H * 0.3), cx + 250, int(H * 0.82)], fill=red)
    d.polygon([(cx - 340, int(H * 0.2)), (cx + 340, int(H * 0.2)), (cx + 310, int(H * 0.26)), (cx - 310, int(H * 0.26))], fill=(30, 20, 20))
    d.rectangle([cx - 300, int(H * 0.26), cx + 300, int(H * 0.3)], fill=red)
    d.rectangle([cx - 280, int(H * 0.37), cx + 280, int(H * 0.41)], fill=red)


def s_blossom(d, W, H, rng):
    vgrad(d, (0, 0, W, H), (160, 200, 240), (220, 235, 250))
    for _ in range(5):
        x0, y0 = rng.randint(0, W), rng.randint(0, H)
        pts = [(x0, y0)]
        for _ in range(6):
            x0 += rng.randint(-120, 120)
            y0 += rng.randint(-80, 80)
            pts.append((x0, y0))
        d.line(pts, fill=(80, 50, 40), width=12)
        for px, py in pts:
            for _ in range(25):
                bx, by = px + rng.randint(-70, 70), py + rng.randint(-50, 50)
                d.ellipse([bx - 12, by - 12, bx + 12, by + 12], fill=rng.choice([(255, 190, 210), (250, 170, 200), (255, 220, 230)]))


def s_screenshot(d, W, H, rng):
    d.rectangle([0, 0, W, H], fill=(32, 34, 40))
    d.rectangle([0, 0, W, 40], fill=(50, 52, 60))
    for k, c in enumerate([(240, 90, 80), (240, 190, 60), (90, 200, 90)]):
        d.ellipse([12 + k * 24, 12, 28 + k * 24, 28], fill=c)
    d.rectangle([0, 40, 240, H], fill=(40, 42, 50))
    f = font(18)
    for k in range(12):
        d.text((20, 70 + k * 34), rng.choice(["src/", "tests/", "api.py", "library.py", "README.md", "index.ts"]), fill=(170, 170, 180), font=f)
    for k in range(22):
        d.text((270, 60 + k * 30), rng.choice(["def search(query, filters):", "    rows = self._rows()", "return payload",
                                               "ERROR 500 image input is not supported", "import numpy as np", "# TODO: cache",
                                               "for n, r in enumerate(top):"]), fill=rng.choice([(200, 200, 210), (120, 200, 250), (250, 150, 120)]), font=f)


def s_scan(d, W, H, rng):
    d.rectangle([0, 0, W, H], fill=(235, 225, 200))
    m = 50
    vgrad(d, (m, m, W - m, H - m), (170, 140, 100), (120, 95, 65))
    for k in range(rng.randint(2, 4)):  # people-shaped silhouettes
        cx = int(W * (0.25 + k * 0.2))
        d.ellipse([cx - 40, int(H * 0.3), cx + 40, int(H * 0.42)], fill=(200, 170, 130))
        d.rectangle([cx - 55, int(H * 0.42), cx + 55, int(H * 0.85)], fill=(70, 50, 35))


SCENES = {
    "sunset": s_sunset, "beach": s_beach, "city_night": s_city_night, "mountain": s_mountain,
    "forest": s_forest, "whiteboard": s_whiteboard, "receipt": s_receipt, "food": s_food,
    "cake": s_cake, "concert": s_concert, "clapper": s_clapper, "greenscreen": s_greenscreen,
    "portrait": s_portrait, "cat": s_cat, "torii": s_torii, "blossom": s_blossom,
    "screenshot": s_screenshot, "scan": s_scan,
}


def render(scene: str, rng: random.Random, size=(1600, 1200), seed=0, **kw) -> Image.Image:
    W, H = size
    img = Image.new("RGB", size, (0, 0, 0))
    SCENES[scene](ImageDraw.Draw(img), W, H, rng, **kw)
    if scene != "screenshot":
        img = img.filter(ImageFilter.GaussianBlur(1.2))
        img = grain(img, seed)
    return img


class Builder:
    def __init__(self, out: Path, seed: int):
        self.out = out
        self.rng = random.Random(seed)
        self.n = 0
        self.counts: dict[str, int] = {}
        self.index: list[dict] = []

    def save(self, rel: str, img: Image.Image, taken: dt.datetime | None, scene: str, *, cam=PHONE,
             gps=None, offset="+02:00", fmt="JPEG", quality=88, exif=True, orientation=None) -> Path:
        path = self.out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        kw = {}
        if fmt == "JPEG":
            kw = {"quality": quality}
            if exif and taken:
                kw["exif"] = exif_bytes(taken, cam, gps, offset, orientation)
        img.save(path, format=fmt, **kw)
        if taken:  # file time = capture time, like a phone copy
            ts = taken.timestamp()
            os.utime(path, (ts, ts))
        self.n += 1
        top = rel.split("/")[0]
        self.counts[top] = self.counts.get(top, 0) + 1
        self.index.append({"path": rel, "scene": scene, "taken": taken.isoformat() if taken else None,
                           "gps": bool(gps and exif), "fmt": fmt})
        return path

    def photo(self, folder: str, taken: dt.datetime, scene: str, place=None, cam=PHONE, offset="+02:00",
              portrait=False, big=False, name=None, **kw) -> Path:
        size = (1200, 1600) if portrait else (1600, 1200)
        if big:
            size = (3000, 4000) if portrait else (4000, 3000)
        img = render(scene, self.rng, size, seed=self.n)
        gps = jitter(PLACES[place], self.rng) if place else None
        stem = name or taken.strftime("IMG_%Y%m%d_%H%M%S")
        return self.save(f"{folder}/{stem}.jpg", img, taken, scene, cam=cam, gps=gps, offset=offset, **kw)


def build(out: Path, seed: int) -> dict:
    if out.exists():
        shutil.rmtree(out)
    b = Builder(out, seed)
    rng = b.rng

    # --- Camera roll: everyday life in Madrid, 2023-2025 --------------------
    daily = ["food", "cat", "portrait", "whiteboard", "receipt", "city_night", "cake", "forest", "concert", "sunset"]
    for i in range(70):
        taken = dt.datetime(2023, 1, 5) + dt.timedelta(days=rng.randint(0, 1000), hours=rng.randint(8, 22), minutes=rng.randint(0, 59))
        scene = daily[i % len(daily)]
        place = "home" if scene in ("food", "cat", "cake") else ("madrid" if rng.random() < 0.7 else None)
        cam = OLDPHONE if taken.year == 2023 else PHONE
        b.photo(f"Camera Roll/{taken.year}/{taken.month:02d}", taken, scene, place, cam=cam,
                portrait=scene in ("portrait", "receipt") or rng.random() < 0.2)
    # "On this day": 22 September in three earlier years
    for y, scene in ((2023, "cat"), (2024, "sunset"), (2025, "cake")):
        b.photo(f"Camera Roll/{y}/09", dt.datetime(y, 9, 22, 19, 30), scene, "home")

    # --- Lisbon trip, July 2024 (camera + phone, GPS, +01:00) ---------------
    start = dt.datetime(2024, 7, 12, 9, 0)
    trip = ["city_night", "sunset", "food", "portrait", "beach", "sunset", "food", "city_night"]
    for i in range(40):
        taken = start + dt.timedelta(days=i // 8, hours=(i % 8) * 1.6, minutes=rng.randint(0, 40))
        scene = trip[i % len(trip)]
        cam = CAMERA if i % 3 == 0 else PHONE
        b.photo("Camera Roll/2024/07", taken, scene, "belem" if scene == "beach" else "lisbon",
                cam=cam, offset="+01:00", big=(cam is CAMERA and i % 2 == 0))
    # the burst: 12 frames of the dog on the beach within 3 seconds
    t0 = dt.datetime(2024, 7, 14, 18, 32, 1)
    burst_rng_state = rng.random()
    for k in range(12):
        brng = random.Random(burst_rng_state)  # identical composition...
        img = render("beach", brng, (1600, 1200), seed=900 + k, dog=True, dx=k * 6, dy=(k % 3) * 3)  # ...dog moves a bit
        taken = t0 + dt.timedelta(milliseconds=250 * k)
        b.save(f"Camera Roll/2024/07/IMG_20240714_183201_BURST{k + 1:03d}.jpg", img, taken, "beach_dog_burst",
               gps=jitter(PLACES["belem"], rng, 0.05), offset="+01:00")
    # two more dog photos that are not part of the burst
    for k, h in ((0, 11), (1, 16)):
        brng = random.Random(4242 + k)
        img = render("beach", brng, (1600, 1200), seed=950 + k, dog=True, dx=-300 + k * 500, dy=-40)
        b.save(f"Camera Roll/2024/07/IMG_2024071{5 + k}_{h}0512.jpg", img, dt.datetime(2024, 7, 15 + k, h, 5, 12),
               "beach_dog", gps=jitter(PLACES["belem"], rng), offset="+01:00")

    # --- Tokyo + Kyoto, April 2025 (+09:00; Kyoto is not a bundled city) -----
    start = dt.datetime(2025, 4, 2, 8, 0)
    jp = ["torii", "blossom", "city_night", "food", "blossom", "torii", "portrait"]
    for i in range(42):
        taken = start + dt.timedelta(days=i // 6, hours=(i % 6) * 2.2, minutes=rng.randint(0, 50))
        place = "kyoto" if 3 <= i // 6 <= 4 else "tokyo"
        b.photo(f"Camera Roll/2025/04", taken, jp[i % len(jp)], place, cam=CAMERA if i % 2 else PHONE, offset="+09:00")

    # --- Cadiz beach day, August 2023: GPS far from every bundled city -------
    for i in range(12):
        taken = dt.datetime(2023, 8, 19, 10, 0) + dt.timedelta(minutes=37 * i)
        b.photo("Camera Roll/2023/08", taken, "beach" if i % 3 else "sunset", "cadiz", cam=OLDPHONE)

    # --- Short film shoot, March 2025 -----------------------------------------
    for i in range(24):
        taken = dt.datetime(2025, 3, 8, 10, 0) + dt.timedelta(minutes=19 * i)
        scene = ["clapper", "greenscreen", "greenscreen", "portrait", "forest"][i % 5]
        b.photo("Rodaje La Estacion", taken, scene, "madrid", cam=CAMERA,
                name=f"OX7_{1200 + i:04d}")

    # --- WhatsApp: downscaled, re-encoded copies, EXIF stripped --------------
    jpgs = sorted((out / "Camera Roll").rglob("*.jpg"))
    for k, src in enumerate(rng.sample(jpgs, 18)):
        with Image.open(src) as im:
            small = im.convert("RGB")
            small.thumbnail((1280, 1280))
            t = dt.datetime.fromtimestamp(src.stat().st_mtime) + dt.timedelta(days=rng.randint(0, 3))
            b.save(f"WhatsApp Images/IMG-{t:%Y%m%d}-WA{k:04d}.jpg", small, t, "whatsapp_copy", exif=False, quality=70)

    # --- Backup: byte-identical copies of a phone dump -----------------------
    for src in rng.sample(jpgs, 15):
        dst = out / "Copia movil 2024" / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        b.n += 1
        b.counts["Copia movil 2024"] = b.counts.get("Copia movil 2024", 0) + 1

    # --- Screenshots (PNG, no EXIF) -----------------------------------------
    for i in range(12):
        t = dt.datetime(2025, 3, 1, 9) + dt.timedelta(days=rng.randint(0, 150), minutes=rng.randint(0, 600))
        img = render("screenshot", rng, (1920, 1080), seed=b.n)
        b.save(f"Screenshots/Captura de pantalla {t:%Y-%m-%d %H%M%S}.png", img, t, "screenshot", fmt="PNG")

    # --- Grandmother's scans: TIFF, no EXIF, sepia, file time = scan day -----
    for i in range(8):
        img = render("scan", rng, (1400, 1000), seed=b.n)
        b.save(f"Escaneos abuela/scan_{i + 1:03d}.tif", img, dt.datetime(2022, 11, 20, 17, i), "scan", fmt="TIFF")

    # --- Misc: the awkward files real folders contain ------------------------
    misc = out / "Varios"
    misc.mkdir(parents=True, exist_ok=True)
    good = render("mountain", rng, (1600, 1200), seed=b.n)
    b.save("Varios/mountain_rotated.jpg", good.rotate(90, expand=True), dt.datetime(2024, 2, 10, 12), "mountain",
           orientation=6)
    b.save("Varios/snow_trip.webp", render("mountain", rng, (1600, 1200), seed=b.n + 1), dt.datetime(2024, 2, 11, 12), "mountain", fmt="WEBP")
    b.save("Varios/cat_phone.heic", render("cat", rng, (1200, 1600), seed=b.n + 2), dt.datetime(2025, 6, 1, 9), "cat", fmt="HEIF")
    frames = [render("concert", random.Random(k), (800, 600), seed=k) for k in range(3)]
    frames[0].save(misc / "concierto.gif", save_all=True, append_images=frames[1:], duration=300)
    b.n += 1
    data = (out / "Camera Roll/2024/07").glob("*.jpg")
    trunc = next(iter(sorted(data))).read_bytes()
    (misc / "IMG_truncated.jpg").write_bytes(trunc[: len(trunc) // 3])
    (misc / "empty.jpg").write_bytes(b"")
    Image.new("RGB", (32, 32), (200, 0, 0)).save(misc / "icon.png")
    (misc / "notas.txt").write_text("lista de fotos para imprimir\n", encoding="utf-8")
    (misc / "DSC_0001.dng").write_bytes(os.urandom(64 * 1024))
    (misc / "._IMG_0001.jpg").write_bytes(os.urandom(4096))   # macOS resource-fork junk
    b.n += 6
    b.counts["Varios"] = b.counts.get("Varios", 0) + 7

    (out.parent / "photos_index.json").write_text(json.dumps(b.index, indent=1), encoding="utf-8")
    return {"files": b.n, "per_folder": b.counts}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=REPO / "data-uxtest" / "photos" / "Pictures")
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()
    random.seed(args.seed)
    import pillow_heif  # HEIC sample; part of the app's lock

    pillow_heif.register_heif_opener()
    summary = build(args.out.resolve(), args.seed)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

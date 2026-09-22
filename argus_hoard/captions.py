"""Optional local captioning of photos through a vision-capable model.

Off by default. Never blocks indexing: a caption is only generated on
explicit request (`photos_describe(caption=true)`) or a user-started batch
job. Two ways to reach a model:

- `OllamaCaptioner`: a direct, private connection to one Ollama server
  (this app's original implementation, kept for anyone still wiring things
  up by hand and exercised directly by the tests below).
- `LinkCaptioner`: the one `Library._captioner()` actually returns. It
  captions through Hoard Link's `vision` capability, so it shares whatever
  server Faustus or a loopback probe resolves (Ollama, llama.cpp, an
  OpenAI-compatible server) instead of only ever speaking Ollama's
  `/api/generate`. See `argus_hoard/backend.py` for how the legacy
  Ollama URL/model settings become that capability's explicit override.

If nothing resolves we say so instead of failing silently.
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable
from urllib.parse import urlparse

import httpx

if TYPE_CHECKING:
    from .hoard_link import Link

DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5vl:7b"
PROMPT = "Describe this photo in one concise sentence, mentioning the main subject and setting."


@dataclass
class CaptionResult:
    ok: bool
    caption: str | None = None
    error: str | None = None


MAX_SIDE = 1024  # vision models downscale anyway; do not ship a 16 MP original


def _downscaled_jpeg_bytes(image_path: Path) -> bytes:
    """A vision-model-friendly JPEG: EXIF-rotated, long side <= MAX_SIDE."""
    from PIL import Image, ImageOps

    with Image.open(image_path) as img:
        try:
            img.draft("RGB", (MAX_SIDE, MAX_SIDE))
        except Exception:  # noqa: BLE001
            pass
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _encode_for_model(image_path: Path) -> str:
    return base64.b64encode(_downscaled_jpeg_bytes(image_path)).decode("ascii")


class OllamaCaptioner:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, model: str = DEFAULT_MODEL, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        host = urlparse(self.base_url).hostname or ""
        # a local Ollama must not be routed through a system proxy
        self._trust_env = host not in ("127.0.0.1", "localhost", "::1")

    def test_connection(self, client: httpx.Client | None = None) -> CaptionResult:
        try:
            own_client = client is None
            c = client or httpx.Client(timeout=5.0, trust_env=self._trust_env)
            try:
                resp = c.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                models = [m.get("name", "") for m in resp.json().get("models", [])]
            finally:
                if own_client:
                    c.close()
            if self.model not in models and models:
                return CaptionResult(ok=False, error=f"model '{self.model}' not found; available: {', '.join(models[:5])}")
            return CaptionResult(ok=True)
        except httpx.HTTPError as exc:
            return CaptionResult(ok=False, error=f"cannot reach Ollama at {self.base_url}: {exc}")

    def caption(self, image_path: Path, client: httpx.Client | None = None) -> CaptionResult:
        try:
            data = _encode_for_model(image_path)
            payload = {
                "model": self.model,
                "prompt": PROMPT,
                "images": [data],
                "stream": False,
            }
            own_client = client is None
            c = client or httpx.Client(timeout=self.timeout, trust_env=self._trust_env)
            try:
                resp = c.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                text = resp.json().get("response", "").strip()
                if not text:
                    return CaptionResult(ok=False, error="Ollama returned an empty caption")
                return CaptionResult(ok=True, caption=text)
            finally:
                if own_client:
                    c.close()
        except httpx.HTTPError as exc:
            return CaptionResult(ok=False, error=f"Ollama request failed: {exc}")
        except (OSError, ValueError) as exc:
            return CaptionResult(ok=False, error=f"could not read image: {exc}")


NO_VISION_MODEL = (
    "No vision model is loaded. Faustus can serve one, or load one in Ollama."
)


class LinkCaptioner:
    """Captions through Hoard Link's `vision` capability.

    This is what `Library._captioner()` returns. It shares whatever server
    Faustus or a loopback probe resolves for `vision` -- Ollama, a
    llama.cpp vision build or an OpenAI-compatible server -- via
    `Link.chat(images=..., capability="vision")`, rather than a private
    connection to one hard-coded Ollama address.
    """

    def __init__(self, link: "Link | Callable[[], Link]"):
        # A callable is re-read on every call, so a long batch follows a
        # Re-check / settings change instead of pinning the replaced Link.
        self._link = link

    @property
    def link(self) -> "Link":
        return self._link() if callable(self._link) else self._link

    def test_connection(self) -> CaptionResult:
        from .hoard_link import BackendError, Unavailable  # noqa: F401 (documents the pair)

        try:
            res = self.link.sync.resolve("vision")
        except Exception as exc:  # noqa: BLE001 - a probe must never crash Settings
            return CaptionResult(ok=False, error=str(exc))
        if not res.resolved:
            return CaptionResult(ok=False, error=f"{NO_VISION_MODEL} ({res.reason})")
        return CaptionResult(ok=True)

    def caption(self, image_path: Path) -> CaptionResult:
        from .hoard_link import BackendError, Unavailable

        try:
            image_bytes = _downscaled_jpeg_bytes(image_path)
        except (OSError, ValueError) as exc:
            return CaptionResult(ok=False, error=f"could not read image: {exc}")
        try:
            result = self.link.sync.chat(
                [{"role": "user", "content": PROMPT}],
                images=[image_bytes],
                max_tokens=200,
                temperature=0.2,
                capability="vision",
            )
        except Unavailable as exc:
            return CaptionResult(ok=False, error=f"{NO_VISION_MODEL} ({'; '.join(exc.reasons)})")
        except BackendError as exc:
            return CaptionResult(ok=False, error=str(exc))
        text = (result.text or "").strip()
        if not text:
            return CaptionResult(ok=False, error="the vision model returned an empty caption")
        return CaptionResult(ok=True, caption=text)

"""Optional local captioning via an Ollama vision model.

Off by default. Never blocks indexing: a caption is only generated on
explicit request (`photos_describe(caption=true)`) or a user-started batch
job. If Ollama is unreachable we say so instead of failing silently.
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5vl:7b"
PROMPT = "Describe this photo in one concise sentence, mentioning the main subject and setting."


@dataclass
class CaptionResult:
    ok: bool
    caption: str | None = None
    error: str | None = None


MAX_SIDE = 1024  # vision models downscale anyway; do not ship a 16 MP original


def _encode_for_model(image_path: Path) -> str:
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
    return base64.b64encode(buf.getvalue()).decode("ascii")


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

"""End-to-end proof that the MCP adapter works: spawns mcp_server.py over
stdio (exactly as Faustus would) against a real, running instance of the
app, and drives it through the real MCP protocol -- not by importing the
adapter's functions directly."""
from __future__ import annotations

import base64
import json
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from daguerre_hoard.api import create_app
from daguerre_hoard.embeddings import FakeEmbedder
from tests.conftest import make_image

REPO_ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture()
def running_app(tmp_path, monkeypatch):
    monkeypatch.setattr("daguerre_hoard.library.select_embedder", lambda settings: FakeEmbedder())
    port = _free_port()
    app = create_app(data_dir=tmp_path / "data", static_dir=None, port=port)

    photos_dir = tmp_path / "photos"
    make_image(photos_dir / "red.jpg", color=(220, 20, 20))
    lib = app.state.library
    root = lib.add_root(str(photos_dir))
    job_id = lib.start_scan(root["id"])
    deadline = time.time() + 10
    while time.time() < deadline:
        job = lib.jobs.get(job_id)
        if job and job["status"] == "done":
            break
        time.sleep(0.02)
    else:
        raise TimeoutError("demo indexing did not finish")

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{base_url}/api/health", timeout=0.5)
            if resp.status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.05)
    else:
        raise TimeoutError("app did not become ready")

    yield base_url

    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.asyncio
async def test_mcp_adapter_over_stdio(running_app):
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(REPO_ROOT / "daguerre_hoard" / "mcp_server.py")],
        env={"DAGUERRE_URL": running_app},
        cwd=str(REPO_ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert names == {
                "photos_search", "photos_similar", "photos_show", "photos_describe",
                "photos_duplicates", "photos_timeline", "photos_library",
                "photos_add_folder", "photos_album",
            }
            for tool in tools.tools:
                assert "Keywords:" in tool.description, tool.name
                assert tool.annotations is not None and tool.annotations.openWorldHint is False, tool.name
                assert tool.annotations.destructiveHint is False, tool.name
            read_only = {t.name for t in tools.tools if t.annotations.readOnlyHint}
            assert read_only == names - {"photos_add_folder", "photos_album"}
            search_tool = next(t for t in tools.tools if t.name == "photos_search")
            assert search_tool.inputSchema["properties"]["orientation"]["anyOf"][0]["enum"] == ["landscape", "portrait"]

            # B1 (live report): a default search/similar call must never carry
            # an image -- a text-only model's turn failed the moment one did.
            result = await session.call_tool("photos_search", {"query": "a red square", "limit": 5})
            assert result.isError is not True
            text_blocks = [c for c in result.content if c.type == "text"]
            image_blocks = [c for c in result.content if c.type == "image"]
            assert len(text_blocks) == 1 and len(image_blocks) == 0
            payload = json.loads(text_blocks[0].text)
            assert payload["results"][0]["n"] == 1
            assert payload["results"][0]["path"].endswith("red.jpg")
            assert payload["results"][0]["relevance"] in ("strong", "medium", "weak")
            assert "contact_sheet_jpeg_base64" not in payload
            assert payload["returned"] == payload["indexed_total"] == len(payload["results"])
            photo_id = payload["results"][0]["id"]

            # Only a call that explicitly asks for it (a multimodal turn) gets one.
            with_sheet = await session.call_tool(
                "photos_search", {"query": "a red square", "limit": 5, "contact_sheet": True}
            )
            sheet_images = [c for c in with_sheet.content if c.type == "image"]
            assert len(sheet_images) == 1
            assert sheet_images[0].mimeType == "image/jpeg"
            assert len(base64.b64decode(sheet_images[0].data)) <= 200 * 1024

            similar_default = await session.call_tool("photos_similar", {"photo_id": photo_id})
            assert [c.type for c in similar_default.content] == ["text"]

            shown = await session.call_tool("photos_show", {"ids": [photo_id, "0" * 32]})
            assert shown.isError is not True
            meta = json.loads(shown.content[0].text)
            assert meta["shown"][0]["id"] == photo_id and meta["not_found"] == ["0" * 32]
            assert [c.type for c in shown.content] == ["text", "image"]

            album = await session.call_tool("photos_album", {"name": "Reds", "photo_ids": [photo_id]})
            assert json.loads(album.content[0].text)["added"] == 1

            timeline = await session.call_tool("photos_timeline", {})
            assert "years" in json.loads(timeline.content[0].text)

            lib_result = await session.call_tool("photos_library", {})
            assert lib_result.isError is not True
            assert json.loads(lib_result.content[0].text)["photo_count"] == 1

            bad_result = await session.call_tool("photos_describe", {"photo_id": "nope"})
            assert bad_result.isError is True
            assert "not_found:" in bad_result.content[0].text
            assert "photos_search" in bad_result.content[0].text  # tells the model how to recover

            bad_filter = await session.call_tool("photos_search", {"query": "x", "month": 13})
            assert bad_filter.isError is True and "invalid_argument" in bad_filter.content[0].text


@pytest.mark.asyncio
async def test_mcp_adapter_reports_app_not_running(tmp_path):
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(REPO_ROOT / "daguerre_hoard" / "mcp_server.py")],
        env={"DAGUERRE_URL": f"http://127.0.0.1:{_free_port()}"},
        cwd=str(tmp_path),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("photos_library", {})
            assert result.isError is True
            assert "daguerre_unavailable" in result.content[0].text
            assert "Iniciar Daguerre.cmd" in result.content[0].text

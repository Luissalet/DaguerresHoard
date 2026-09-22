"""End-to-end proof that the MCP adapter works: spawns mcp_server.py over
stdio (exactly as Faustus would) against a real, running instance of the
app, and drives it through the real MCP protocol -- not by importing the
adapter's functions directly."""
from __future__ import annotations

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

from argus_hoard.api import create_app
from argus_hoard.embeddings import FakeEmbedder
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
    monkeypatch.setattr("argus_hoard.library.select_embedder", lambda settings: FakeEmbedder())
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
        args=[str(REPO_ROOT / "argus_hoard" / "mcp_server.py")],
        env={"ARGUS_URL": running_app},
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
            search_tool = next(t for t in tools.tools if t.name == "photos_search")
            assert "Keywords:" in search_tool.description
            assert search_tool.annotations.readOnlyHint is True

            result = await session.call_tool("photos_search", {"query": "a red square", "limit": 5})
            assert result.isError is not True
            assert len(result.content) >= 2  # structured dict text block + contact sheet image
            text_blocks = [c for c in result.content if c.type == "text"]
            image_blocks = [c for c in result.content if c.type == "image"]
            assert text_blocks and "red.jpg" in text_blocks[0].text
            assert image_blocks

            lib_result = await session.call_tool("photos_library", {})
            assert lib_result.isError is not True

            bad_result = await session.call_tool("photos_describe", {"photo_id": "nope"})
            assert bad_result.isError is True

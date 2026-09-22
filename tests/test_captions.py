import httpx
import pytest

from argus_hoard.captions import OllamaCaptioner


def _mock_transport(response_json, status_code=200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=response_json)

    return httpx.MockTransport(handler)


def test_caption_success(tmp_path, monkeypatch):
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"\xff\xd8\xff\xd9")  # minimal fake bytes, not decoded here

    captioner = OllamaCaptioner(base_url="http://127.0.0.1:11434", model="qwen2.5vl:7b")
    client = httpx.Client(transport=_mock_transport({"response": "A red square on a beach."}))
    result = captioner.caption(img, client=client)
    assert result.ok
    assert "red square" in result.caption


def test_caption_ollama_unreachable(tmp_path):
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"\xff\xd8\xff\xd9")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    captioner = OllamaCaptioner(base_url="http://127.0.0.1:11434")
    result = captioner.caption(img, client=client)
    assert not result.ok
    assert "Ollama" in result.error


def test_connection_check_reports_missing_model():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "llama3"}]})

    captioner = OllamaCaptioner(model="qwen2.5vl:7b")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = captioner.test_connection(client=client)
    assert not result.ok
    assert "qwen2.5vl:7b" in result.error


def test_connection_check_ok_when_model_present():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "qwen2.5vl:7b"}]})

    captioner = OllamaCaptioner(model="qwen2.5vl:7b")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = captioner.test_connection(client=client)
    assert result.ok

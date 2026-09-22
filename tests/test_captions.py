import httpx

from argus_hoard.captions import OllamaCaptioner
from tests.conftest import make_image


def _mock_transport(response_json, status_code=200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=response_json)

    return httpx.MockTransport(handler)


def test_caption_success(tmp_path, monkeypatch):
    import base64
    import io
    import json

    from PIL import Image

    img = make_image(tmp_path / "photo.jpg", size=(3000, 2000))
    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent["model"] = body["model"]
        sent["size"] = Image.open(io.BytesIO(base64.b64decode(body["images"][0]))).size
        return httpx.Response(200, json={"response": "A red square on a beach."})

    captioner = OllamaCaptioner(base_url="http://127.0.0.1:11434", model="qwen2.5vl:7b")
    result = captioner.caption(img, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert result.ok
    assert "red square" in result.caption
    assert sent["model"] == "qwen2.5vl:7b"
    assert max(sent["size"]) <= 1024  # the 6 MP original is downscaled before sending


def test_caption_ollama_unreachable(tmp_path):
    img = make_image(tmp_path / "photo.jpg")

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

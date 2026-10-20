"""Transport tier: the playground server's routing, validation and error mapping, with the registry mocked."""

import http.client
import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
import serve

from memo_extract.registry import NotFound


class RegistryStub:
    def __init__(self):
        self.calls = []

    def models(self):
        return [{"id": "m:torch"}]

    def run(self, model_id, texts, today, contacts, day_first):
        self.calls.append((model_id, texts, today, contacts, day_first))
        if model_id == "missing":
            raise NotFound("Model not found: missing")
        if model_id == "broken":
            raise KeyError("a bug, not a missing model")
        return [{"ms": 1.0, "spans": [], "suggestions": {}} for _ in texts]


@pytest.fixture
def ctx(tmp_path):
    registry = RegistryStub()
    serve.Handler.registry = registry
    serve.Handler.prompts = serve.Prompts(tmp_path / "prompts.json")
    server = ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield {"port": server.server_address[1], "registry": registry}
    server.shutdown()


def request(ctx, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", ctx["port"], timeout=5)
    payload = json.dumps(body).encode() if body is not None else None
    conn.request(method, path, body=payload, headers=headers or {})
    res = conn.getresponse()
    return res.status, json.loads(res.read() or b"null")


VALID = {"models": ["m:torch"], "texts": ["Sam's test is Friday"], "today": "2026-10-19"}


def test_predict_passes_parsed_inputs_to_the_registry(ctx):
    status, body = request(ctx, "POST", "/api/predict", {**VALID, "contacts": [" Sam Lee ", ""], "day_first": False})

    assert status == 200
    assert list(body) == ["m:torch"]
    ((_, texts, today, contacts, day_first),) = ctx["registry"].calls
    assert (texts, str(today), contacts, day_first) == (["Sam's test is Friday"], "2026-10-19", ["Sam Lee"], False)


@pytest.mark.parametrize(
    "override, message",
    [
        ({"texts": []}, "texts"),
        ({"texts": [" "]}, "texts"),
        ({"models": []}, "models"),
        ({"today": 1}, "today"),
        ({"today": "19/10/2026"}, "today"),
        ({"contacts": [1]}, "contacts"),
        ({"contacts": "Sam"}, "contacts"),
        ({"day_first": "false"}, "day_first"),
    ],
)
def test_invalid_input_is_a_client_error_and_nothing_runs(ctx, override, message):
    status, body = request(ctx, "POST", "/api/predict", {**VALID, **override})

    assert status == 400
    assert message in body["error"]
    assert ctx["registry"].calls == []


def test_negative_content_length_is_rejected(ctx):
    status, body = request(ctx, "POST", "/api/predict", None, {"Content-Length": "-1"})

    assert status == 400
    assert "Content-Length" in body["error"]


def test_unknown_model_is_not_found(ctx):
    status, body = request(ctx, "POST", "/api/predict", {**VALID, "models": ["missing"]})

    assert (status, body["error"]) == (404, "Model not found: missing")


def test_a_bug_is_a_server_error_not_a_404(ctx):
    status, _ = request(ctx, "POST", "/api/predict", {**VALID, "models": ["broken"]})

    assert status == 500


def test_prompts_round_trip(ctx):
    _, created = request(ctx, "POST", "/api/prompts", {"text": "  Sam's test is Friday ", "note": "n"})
    _, listed = request(ctx, "GET", "/api/prompts")
    status, _ = request(ctx, "DELETE", f"/api/prompts/{created['id']}")
    missing, _ = request(ctx, "DELETE", f"/api/prompts/{created['id']}")

    assert listed == [{"id": created["id"], "text": "Sam's test is Friday", "note": "n"}]
    assert (status, missing) == (200, 404)

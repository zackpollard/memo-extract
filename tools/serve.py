#!/usr/bin/env python3
"""Model playground: tools/serve.py [--port 8765] [--host 127.0.0.1] [--threads 1], then open http://127.0.0.1:8765

Lists every PyTorch run in runs/ and every ONNX export in models/onnx/ (re-scanned on each request, so new
models show up on refresh). Saved prompts live in playground/prompts.json so they are shared and versioned.
"""

import argparse
import json
import logging
import threading
import uuid
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import _path  # noqa: F401
import torch

from memo_extract.registry import NotFound, Registry

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "playground" / "index.html"
PROMPTS = ROOT / "playground" / "prompts.json"
MAX_BODY_BYTES = 1_000_000
MAX_BATCH_TEXTS = 500

log = logging.getLogger("playground")


class ClientError(Exception):
    pass


class Prompts:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()

    def all(self):
        return json.loads(self.path.read_text()) if self.path.exists() else []

    def add(self, text, note):
        with self.lock:
            prompts = self.all()
            prompt = {"id": uuid.uuid4().hex[:8], "text": text, "note": note}
            self.write([*prompts, prompt])
            return prompt

    def remove(self, prompt_id):
        with self.lock:
            prompts = self.all()
            if not any(p["id"] == prompt_id for p in prompts):
                raise NotFound("Prompt not found")
            self.write([p for p in prompts if p["id"] != prompt_id])

    def write(self, prompts):
        self.path.write_text(json.dumps(prompts, indent=2, ensure_ascii=False) + "\n")


def predict(registry, body):
    texts = body.get("texts")
    model_ids = body.get("models")
    if not isinstance(texts, list) or not texts or not all(isinstance(t, str) and t.strip() for t in texts):
        raise ClientError("texts must be a non-empty list of memos")
    if len(texts) > MAX_BATCH_TEXTS:
        raise ClientError(f"At most {MAX_BATCH_TEXTS} memos per request")
    if not isinstance(model_ids, list) or not model_ids:
        raise ClientError("models must be a non-empty list of model ids")

    today = body.get("today") or date.today().isoformat()
    contacts = body.get("contacts") or []
    day_first = body.get("day_first", True)
    if not isinstance(today, str):
        raise ClientError("today must be an ISO date string")
    if not isinstance(contacts, list) or not all(isinstance(c, str) for c in contacts):
        raise ClientError("contacts must be a list of names")
    if not isinstance(day_first, bool):
        raise ClientError("day_first must be true or false")
    try:
        today = date.fromisoformat(today)
    except ValueError:
        raise ClientError("today must be an ISO date") from None
    contacts = [c.strip() for c in contacts if c.strip()] or None
    return {model_id: registry.run(model_id, texts, today, contacts, day_first) for model_id in model_ids}


class Handler(BaseHTTPRequestHandler):
    registry: Registry
    prompts: Prompts

    def do_GET(self):
        self.dispatch(lambda: self.route_get())

    def do_POST(self):
        self.dispatch(lambda: self.route_post(self.read_body()))

    def do_DELETE(self):
        self.dispatch(lambda: self.route_delete())

    def route_get(self):
        if self.path in ("/", "/index.html"):
            return self.send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/models":
            return self.send_json(200, self.registry.models())
        if self.path == "/api/prompts":
            return self.send_json(200, self.prompts.all())
        raise NotFound("Not found")

    def route_post(self, body):
        if self.path == "/api/predict":
            return self.send_json(200, predict(self.registry, body))
        if self.path == "/api/prompts":
            text = body.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ClientError("text is required")
            return self.send_json(201, self.prompts.add(text.strip(), str(body.get("note") or "").strip()))
        raise NotFound("Not found")

    def route_delete(self):
        if not self.path.startswith("/api/prompts/"):
            raise NotFound("Not found")
        self.prompts.remove(self.path.removeprefix("/api/prompts/"))
        return self.send_json(200, {"ok": True})

    def read_body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ClientError("Content-Length must be a number") from None
        if not 0 <= length <= MAX_BODY_BYTES:
            raise ClientError(f"Content-Length must be between 0 and {MAX_BODY_BYTES}")
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            raise ClientError("Body must be JSON") from None
        if not isinstance(body, dict):
            raise ClientError("Body must be a JSON object")
        return body

    def dispatch(self, handler):
        """The one place that turns exceptions into status codes."""
        try:
            handler()
        except ClientError as e:
            self.send_json(400, {"error": str(e)})
        except NotFound as e:
            log.debug("not found: %s", e)
            self.send_json(404, {"error": str(e)})
        except (BrokenPipeError, ConnectionResetError):
            log.debug("client went away")
        except Exception:
            log.exception("request failed: %s %s", self.command, self.path)
            self.send_json(500, {"error": "Internal error, see server log"})

    def send_json(self, status, payload):
        self.send(status, json.dumps(payload, ensure_ascii=False).encode(), "application/json")

    def send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        log.debug(fmt, *args)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--threads", type=int, default=1, help="torch/onnx threads per prediction; 1 approximates one phone core")
    ap.add_argument("--runs", default=str(ROOT / "runs"))
    ap.add_argument("--onnx", default=str(ROOT / "models" / "onnx"))
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    torch.set_num_threads(args.threads)
    Handler.registry = Registry(args.runs, args.onnx)
    Handler.prompts = Prompts(PROMPTS)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    log.info("playground on http://%s:%d (%d models)", args.host, args.port, len(Handler.registry.models()))
    server.serve_forever()


if __name__ == "__main__":
    main()

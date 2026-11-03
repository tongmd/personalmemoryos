"""Authenticated loopback RPC for a trusted application gateway."""

from __future__ import annotations

import hashlib
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .store import Conflict, MemoryError, Store, encode, required_text


class Gateway:
    def __init__(self, store: Store, token: str, shared_owner: str):
        if len(token) < 32:
            raise MemoryError("Gateway token must contain at least 32 characters")
        self.store, self.token = store, token
        self.shared_owner = required_text(shared_owner, "shared_owner", 200)

    def for_owner(self, owner: str) -> Store:
        required_text(owner, "owner", 200)
        if owner == self.shared_owner:
            return self.store
        name = hashlib.sha256(owner.encode()).hexdigest()
        store = Store(self.store.path.parent / (self.store.path.name + "-users") / name)
        store.init()
        return store

    def dispatch(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise MemoryError("Request must be an object")
        store = self.for_owner(payload.get("owner"))
        args = payload.get("arguments", {})
        if not isinstance(args, dict):
            raise MemoryError("arguments must be an object")
        operation = payload.get("operation")
        if operation == "snapshot":
            return store.snapshot()
        if operation == "recall":
            return store.recall(**args)
        if operation == "apply":
            return store.apply(**args)
        if operation == "revert":
            return store.revert(**args)
        if operation == "history":
            return {"commits": store.history(**args)}
        raise MemoryError("Unknown memory operation")


def make_server(gateway: Gateway, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self, status: int, value: dict):
            data = encode(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def authorized(self) -> bool:
            actual = self.headers.get("Authorization", "")
            return hmac.compare_digest(actual, "Bearer " + gateway.token)

        def do_GET(self):
            if not self.authorized():
                return self.respond(401, {"error": "Authentication required"})
            if self.path == "/health":
                return self.respond(
                    200, {"status": "ok", "service": "recallos", "revision": gateway.store.head()}
                )
            return self.respond(404, {"error": "Unknown route"})

        def do_POST(self):
            if not self.authorized():
                return self.respond(401, {"error": "Authentication required"})
            if self.path != "/v1/memory":
                return self.respond(404, {"error": "Unknown route"})
            try:
                if self.headers.get("Transfer-Encoding"):
                    raise MemoryError("Chunked requests are not supported")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 100000:
                    raise MemoryError("Request must contain at most 100000 bytes")
                self.connection.settimeout(10)
                payload = json.loads(self.rfile.read(length))
                self.respond(200, gateway.dispatch(payload))
            except Conflict as error:
                self.respond(409, {"status": "conflict", "error": str(error)})
            except (MemoryError, ValueError, TypeError, KeyError, OSError) as error:
                self.respond(400, {"status": "error", "error": str(error)})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve_http(store: Store, port: int, token_file: str, shared_owner: str):
    store.head()
    token_path = Path(token_file).expanduser()
    if token_path.stat().st_mode & 0o077:
        raise MemoryError("Gateway token file must not be readable by group or others")
    server = make_server(Gateway(store, token_path.read_text().strip(), shared_owner), port)
    try:
        server.serve_forever()
    finally:
        server.server_close()

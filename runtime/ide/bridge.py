from __future__ import annotations

import hmac
import json
from dataclasses import dataclass, fields, is_dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Callable
from urllib.parse import urlparse

from runtime.ide.runtime import IDERuntime
from core.contracts.ide import (
    IDECommand, IDECommandKind, IDEContext, IDEEvent, IDEEventKind, IDEKind, IDEWorkRequest,
)


class IDEBridgeAuthorizationError(PermissionError):
    pass


@dataclass(frozen=True)
class IDEBridgePolicy:
    token: str
    max_body_bytes: int = 256 * 1024
    allow_remote: bool = False

    def authorize(self, supplied: str | None) -> None:
        if not self.token or not supplied or not hmac.compare_digest(self.token, supplied):
            raise IDEBridgeAuthorizationError("invalid VYRELON IDE bridge token")


class IDEBridge:
    def __init__(self, *, policy: IDEBridgePolicy,
                 runtime: IDERuntime | None = None,
                 event_handler: Callable[[IDEEvent], object] | None = None,
                 command_handler: Callable[[IDECommand], object] | None = None,
                 work_handler: Callable[[IDEWorkRequest], object] | None = None) -> None:
        self.policy = policy
        self.runtime = runtime
        self.event_handler = event_handler or (lambda event: event)
        self.command_handler = command_handler or (lambda command: command)
        self.work_handler = work_handler

    def handle_event(self, payload: dict[str, object]) -> object:
        event = decode_event(payload)
        if self.runtime is not None:
            return self.runtime.ingest_event(event)
        return self.event_handler(event)

    def handle_work(self, payload: dict[str, object]) -> object:
        request = decode_work_request(payload)
        if self.work_handler is None:
            raise ValueError("IDE work handler is not configured")
        return self.work_handler(request)

    def handle_command(self, payload: dict[str, object]) -> object:
        command = decode_command(payload)
        if self.runtime is not None:
            if command.context is None:
                raise ValueError("command context is required for IDE bridge dispatch")
            return self.runtime.execute(command.context.kind, command)
        return self.command_handler(command)


class _Handler(BaseHTTPRequestHandler):
    bridge: IDEBridge

    def do_POST(self) -> None:  # noqa: N802
        if not self.bridge.policy.allow_remote and self.client_address[0] not in {"127.0.0.1", "::1"}:
            self._respond(403, {"error": "loopback only"})
            return
        token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        try:
            self.bridge.policy.authorize(token)
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > self.bridge.policy.max_body_bytes:
                raise ValueError("invalid request body size")
            payload = json.loads(self.rfile.read(length))
            path = urlparse(self.path).path
            if path == "/v1/ide/event":
                result = self.bridge.handle_event(payload)
            elif path == "/v1/ide/work":
                result = self.bridge.handle_work(payload)
            elif path == "/v1/ide/command":
                result = self.bridge.handle_command(payload)
            else:
                self._respond(404, {"error": "not found"})
                return
            self._respond(200, {"ok": True, "result": _jsonable(result)})
        except IDEBridgeAuthorizationError as exc:
            self._respond(401, {"error": str(exc)})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._respond(400, {"error": str(exc)})
        except Exception as exc:  # pragma: no cover
            self._respond(500, {"error": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _respond(self, status: int, payload: dict[str, object]) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class IDEBridgeServer:
    def __init__(self, bridge: IDEBridge, host: str = "127.0.0.1", port: int = 8787) -> None:
        if host not in {"127.0.0.1", "::1"} and not bridge.policy.allow_remote:
            raise ValueError("IDE bridge must bind to loopback unless remote access is explicitly allowed")
        self.bridge = bridge
        self.server = ThreadingHTTPServer((host, port), _Handler)
        self.server.RequestHandlerClass.bridge = bridge
        self.thread: Thread | None = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        if self.thread:
            self.thread.join(timeout=2)


def _jsonable(value: object) -> object:
    if is_dataclass(value):
        return {item.name: _jsonable(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return str(value)


def _context(payload: dict[str, object]) -> IDEContext:
    raw = payload.get("context")
    if not isinstance(raw, dict):
        raise ValueError("context must be an object")
    return IDEContext(
        kind=IDEKind(str(raw["kind"])),
        project_root=str(raw.get("project_root", "")),
        workspace_id=raw.get("workspace_id"),
        file_path=raw.get("file_path"),
        selection_start=raw.get("selection_start"),
        selection_end=raw.get("selection_end"),
        language_id=raw.get("language_id"),
        metadata=raw.get("metadata", {}),
    )


def decode_event(payload: dict[str, object]) -> IDEEvent:
    return IDEEvent(
        kind=IDEEventKind(str(payload["kind"])),
        context=_context(payload),
        payload=payload.get("payload", {}),
        apply_changes=bool(payload.get("apply_changes", False)),
        validation_commands=tuple(payload.get("validation_commands", [])),
        metadata=payload.get("metadata", {}),
    )


def decode_command(payload: dict[str, object]) -> IDECommand:
    arguments = payload.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    return IDECommand(
        kind=IDECommandKind(str(payload["kind"])),
        arguments=arguments,
        context=_context(payload) if payload.get("context") is not None else None,
        metadata=payload.get("metadata", {}),
    )

    
def decode_work_request(payload: dict[str, object]) -> IDEWorkRequest:
    objective = payload.get("objective")
    agent_id = payload.get("agent_id")
    model_ids = payload.get("model_ids", [])
    if not isinstance(objective, str) or not objective.strip():
        raise ValueError("objective must be a non-empty string")
    if not isinstance(agent_id, str) or not agent_id.strip():
        raise ValueError("agent_id must be a non-empty string")
    if not isinstance(model_ids, list) or not all(isinstance(item, str) for item in model_ids):
        raise ValueError("model_ids must be a list of strings")
    return IDEWorkRequest(
        context=_context(payload),
        objective=objective,
        agent_id=agent_id,
        model_ids=tuple(model_ids),
        metadata=payload.get("metadata", {}),
    )

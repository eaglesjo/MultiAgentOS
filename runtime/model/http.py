"""Generic HTTP JSON model adapter."""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelRequest, ModelResponse
from runtime.policy import ExecutionPolicy


@dataclass(frozen=True)
class HTTPModelAdapter:
    endpoint: str
    headers: dict[str, str] = field(default_factory=dict)
    header_env: dict[str, str] = field(default_factory=dict)
    request_template: dict[str, Any] = field(
        default_factory=lambda: {
            "model": "{model_id}",
            "prompt": "{prompt}",
            "system": "{system}",
        }
    )
    response_path: tuple[str, ...] = ("text",)
    policy: ExecutionPolicy = ExecutionPolicy(allow_network=True)

    def generate(self, model: ModelSpec, request: ModelRequest) -> ModelResponse:
        if not self.policy.permits("network"):
            raise PermissionError("Network model execution is disabled by policy")

        payload = self._render(self.request_template, model, request)
        headers = {"Content-Type": "application/json", **self.headers}
        for header, env_name in self.header_env.items():
            value = os.environ.get(env_name)
            if not value:
                raise RuntimeError(f"Required model credential environment variable is missing: {env_name}")
            headers[header] = value

        body = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(http_request, timeout=300) as response:
            data = json.loads(response.read().decode("utf-8"))

        value: Any = data
        for part in self.response_path:
            if isinstance(value, dict):
                value = value[part]
            elif isinstance(value, list):
                value = value[int(part)]
            else:
                raise ValueError(f"Cannot resolve response path at: {part}")

        if not isinstance(value, str):
            raise ValueError("Configured model response path must resolve to text")

        return ModelResponse(text=value, model_id=model.id, metadata={"adapter": "http"})

    def _render(self, value: Any, model: ModelSpec, request: ModelRequest) -> Any:
        if isinstance(value, str):
            return (
                value.replace("{model_id}", model.id)
                .replace("{prompt}", request.prompt)
                .replace("{system}", request.system or "")
            )
        if isinstance(value, dict):
            return {key: self._render(item, model, request) for key, item in value.items()}
        if isinstance(value, list):
            return [self._render(item, model, request) for item in value]
        return value

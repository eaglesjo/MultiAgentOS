"""Materialize generic model adapters from declarative provider configuration."""

from __future__ import annotations

from typing import Any

from runtime.model.cli import CLIModelAdapter
from runtime.model.http import HTTPModelAdapter
from runtime.policy import ExecutionPolicy


class ConfiguredAdapterFactory:
    """Build only the provider-neutral adapters supported by MultiAgentOS."""

    def build(
        self,
        adapter_id: str,
        metadata: dict[str, object],
        policy: ExecutionPolicy | None = None,
    ):
        kind = str(metadata.get("adapter_kind", adapter_id))
        effective_policy = policy or ExecutionPolicy()

        if kind == "cli":
            command = metadata.get("command")
            if not isinstance(command, list) or not all(
                isinstance(part, str) and part for part in command
            ):
                raise ValueError(
                    f"CLI adapter {adapter_id} requires metadata.command as a non-empty list"
                )
            timeout = metadata.get("timeout", 300)
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                raise ValueError(f"CLI adapter {adapter_id} timeout must be positive")
            return CLIModelAdapter(
                command=tuple(command),
                policy=effective_policy,
                timeout=float(timeout),
            )

        if kind == "http":
            endpoint = metadata.get("endpoint")
            if not isinstance(endpoint, str) or not endpoint:
                raise ValueError(
                    f"HTTP adapter {adapter_id} requires metadata.endpoint"
                )

            headers = self._string_mapping(metadata.get("headers", {}), "headers")
            header_env = self._string_mapping(
                metadata.get("header_env", {}), "header_env"
            )
            request_template = metadata.get("request_template", {})
            if not isinstance(request_template, dict):
                raise ValueError(
                    f"HTTP adapter {adapter_id} request_template must be an object"
                )
            response_path = metadata.get("response_path", ["text"])
            if not isinstance(response_path, list) or not all(
                isinstance(part, str) for part in response_path
            ):
                raise ValueError(
                    f"HTTP adapter {adapter_id} response_path must be a list of strings"
                )
            return HTTPModelAdapter(
                endpoint=endpoint,
                headers=headers,
                header_env=header_env,
                request_template=request_template,
                response_path=tuple(response_path),
                policy=effective_policy,
            )

        raise ValueError(f"Unsupported model adapter kind: {kind}")

    @staticmethod
    def _string_mapping(value: Any, field_name: str) -> dict[str, str]:
        if not isinstance(value, dict) or not all(
            isinstance(key, str) and isinstance(item, str)
            for key, item in value.items()
        ):
            raise ValueError(f"{field_name} must be an object of strings")
        return dict(value)

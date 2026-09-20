"""Generic CLI model adapter for any model exposed by a command-line client."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelRequest, ModelResponse
from runtime.policy import ExecutionPolicy


@dataclass(frozen=True)
class CLIModelAdapter:
    command: tuple[str, ...]
    policy: ExecutionPolicy = ExecutionPolicy()
    timeout: float = 300

    def generate(self, model: ModelSpec, request: ModelRequest) -> ModelResponse:
        if not self.policy.permits("process"):
            raise PermissionError("Model CLI execution is disabled by policy")
        if not self.command or not all(isinstance(part, str) and part for part in self.command):
            raise ValueError("CLI adapter command must be a non-empty argv tuple")

        prompt = request.prompt
        if request.system:
            prompt = f"{request.system}\n\n{prompt}"

        environment = os.environ.copy()
        completed = subprocess.run(
            list(self.command),
            input=prompt,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
            env=environment,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Model CLI failed with exit code {completed.returncode}: {completed.stderr.strip()}"
            )

        return ModelResponse(
            text=completed.stdout,
            model_id=model.id,
            metadata={"adapter": "cli"},
        )

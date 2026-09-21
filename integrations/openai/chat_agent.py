"""OpenAI Chat Agent adapter for VYRELON.

This adapter is optional: the core remains provider-neutral and does not require
an OpenAI SDK or API key at import time.
"""

from __future__ import annotations

import json
import os
from typing import Any

from core.chat_agent_bridge import (
    ChatAgentAdapter,
    ChatAgentRequest,
    ChatAgentResponse,
)
from core.contracts.chat_agent import ChatAgentContract
from core.contracts.planning import PlanStep


class OpenAIChatAgentAdapter:
    """Connect a ChatGPT-class agent to the provider-neutral Chat Agent bridge."""

    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        self.model = model or os.environ.get("VYRELON_OPENAI_MODEL") or os.environ.get(
            "OPENAI_MODEL"
        )
        self._client = client

    def _client_or_create(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI Chat Agent support requires the optional 'openai' package"
            ) from exc
        self._client = OpenAI()
        return self._client

    def respond(
        self,
        *,
        agent: ChatAgentContract,
        instructions: str,
        request: ChatAgentRequest,
    ) -> ChatAgentResponse:
        if not self.model:
            raise ValueError(
                "Set VYRELON_OPENAI_MODEL or OPENAI_MODEL for the OpenAI Chat Agent adapter"
            )

        client = self._client_or_create()
        response = client.responses.create(
            model=self.model,
            instructions=instructions,
            input=self._build_input(request),
        )
        text = getattr(response, "output_text", "") or ""
        parsed = self._parse_structured_response(text, request)
        return ChatAgentResponse(
            summary=parsed["summary"],
            steps=tuple(parsed["steps"]),
            findings=tuple(parsed["findings"]),
            artifacts=tuple(parsed["artifacts"]),
            evidence=(
                f"OpenAI response received from model {self.model}",
            ),
        )

    @staticmethod
    def _build_input(request: ChatAgentRequest) -> str:
        payload = {
            "objective": request.objective,
            "inputs": request.inputs or {},
            "required_output": {
                "summary": "string",
                "steps": [
                    {
                        "id": "string",
                        "objective": "string",
                        "agent_id": "optional string",
                        "depends_on": ["step id"],
                    }
                ],
                "findings": ["string"],
                "artifacts": ["string"],
            },
        }
        return (
            "Return ONLY valid JSON matching this schema. Do not claim that any "
            "filesystem, Git, GitHub, or other external action was performed. "
            "Those actions belong to VYRELON runtime.\n\n"
            + json.dumps(payload, ensure_ascii=False)
        )

    @staticmethod
    def _parse_structured_response(text: str, request: ChatAgentRequest) -> dict[str, Any]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return {
                "summary": text.strip() or "No structured response returned.",
                "steps": [
                    PlanStep(
                        id="chat-understanding",
                        objective=request.objective,
                    )
                ],
                "findings": (),
                "artifacts": (),
            }

        steps = []
        for index, item in enumerate(data.get("steps", []), 1):
            if not isinstance(item, dict):
                continue
            objective = str(item.get("objective", "")).strip()
            if not objective:
                continue
            step_id = str(item.get("id", f"step-{index}")).strip() or f"step-{index}"
            depends_on = tuple(str(value) for value in item.get("depends_on", []))
            steps.append(
                PlanStep(
                    id=step_id,
                    objective=objective,
                    agent_id=item.get("agent_id"),
                    depends_on=depends_on,
                )
            )

        if not steps:
            steps = [
                PlanStep(
                    id="chat-understanding",
                    objective=request.objective,
                )
            ]

        return {
            "summary": str(data.get("summary", "")).strip() or "Plan prepared.",
            "steps": steps,
            "findings": tuple(str(value) for value in data.get("findings", [])),
            "artifacts": tuple(str(value) for value in data.get("artifacts", [])),
        }

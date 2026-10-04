"""Model-backed Agent selection using the existing provider-neutral AI runtime.

Model inference is an implementation strategy behind the Agent-selection boundary.
This component proposes a route only; it never executes an Agent or bypasses policy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from core.agent_selection_policy import SelectionDecision
from core.contracts.agent_selection import AgentCandidate
from core.contracts.evidence import EvidenceRecord
from core.contracts.model_runtime import ModelRequest
from core.contracts.work_unit import WorkUnit
from runtime.model.ai_runtime import AIRuntime


@dataclass(frozen=True)
class ModelBackedAgentSelector:
    """Use an existing AIRuntime model to propose a structured Agent route."""

    runtime: AIRuntime
    model_id: str

    def select(
        self,
        *,
        work_unit: WorkUnit,
        evidence: tuple[EvidenceRecord, ...],
        candidates: tuple[AgentCandidate, ...],
    ) -> SelectionDecision:
        candidate_ids = tuple(candidate.agent_id for candidate in candidates)
        execution = self.runtime.execute(
            ModelRequest(
                prompt=self._prompt(work_unit, evidence, candidates),
                system=(
                    "You are the Agent selection component of MultiAgentOS. "
                    "Choose only from the supplied candidate Agent IDs. "
                    "Return JSON only; do not execute tools or Agents."
                ),
            ),
            model_id=self.model_id,
        )
        return self._parse(execution.response.text, candidate_ids)

    def select_stage(
        self,
        *,
        work_unit: WorkUnit,
        evidence: tuple[EvidenceRecord, ...],
        candidates: tuple[AgentCandidate, ...],
        stage_index: int,
    ) -> SelectionDecision:
        """Select exactly one Agent for one ambiguous stage."""
        decision = self.select(
            work_unit=work_unit,
            evidence=evidence,
            candidates=candidates,
        )
        if len(decision.selected_agents) != 1:
            raise ValueError(
                f"model-backed stage selector must return exactly one Agent for stage {stage_index}"
            )
        return decision

    @staticmethod
    def _ranked_candidates(
        candidates: tuple[AgentCandidate, ...],
    ) -> dict[str, list[dict[str, object]]]:
        """Expose stage-local ranking without allowing the model to invent candidates."""
        ranked: dict[str, list[dict[str, object]]] = {}
        for stage_index in sorted({i for candidate in candidates for i in candidate.stage_indices}):
            stage = [
                candidate for candidate in candidates if stage_index in candidate.stage_indices
            ]
            stage.sort(key=lambda candidate: (-candidate.score, candidate.agent_id))
            ranked[str(stage_index)] = [
                {
                    "agent_id": candidate.agent_id,
                    "score": candidate.score,
                    "reasons": list(candidate.reasons),
                }
                for candidate in stage
            ]
        return ranked

    @staticmethod
    def _prompt(work_unit: WorkUnit, evidence: tuple[EvidenceRecord, ...], candidates: tuple[AgentCandidate, ...]) -> str:
        payload = {
            "work_unit": {
                "id": work_unit.id,
                "objective": work_unit.objective,
                "work_type": work_unit.work_type,
                "target": work_unit.target,
                "environment": work_unit.environment,
                "metadata": dict(work_unit.metadata),
            },
            "evidence": [
                {"id": e.id, "kind": e.kind.value, "source": e.source, "statement": e.statement}
                for e in evidence
            ],
            "candidate_pool": [
                {"agent_id": c.agent_id, "score": c.score, "reasons": list(c.reasons), "stage_indices": list(c.stage_indices)}
                for c in candidates
            ],
            "stage_rankings": ModelBackedAgentSelector._ranked_candidates(candidates),
            "output_schema": {
                "selected_agents": ["candidate-agent-id-for-stage-0", "candidate-agent-id-for-stage-1"],
                "confidence": 0.0,
                "reasons": ["short reason"],
                "constraints": [
                    "select exactly one candidate for each governed stage, in stage order",
                    "use only candidate_pool Agent IDs",
                    "respect each candidate's stage_indices",
                ],
            },
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _parse(text: str, candidate_ids: tuple[str, ...]) -> SelectionDecision:
        cleaned = text.strip()
        fence = chr(96) * 3
        if cleaned.startswith(fence):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith(fence):
                lines = lines[1:]
            if lines and lines[-1].strip() == fence:
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError("model-backed selector response must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("model-backed selector response must be a JSON object")

        selected = payload.get("selected_agents")
        confidence = payload.get("confidence")
        reasons = payload.get("reasons", ())
        if not isinstance(selected, list) or not all(isinstance(item, str) and item for item in selected):
            raise ValueError("model-backed selector response requires selected_agents")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            raise ValueError("model-backed selector response requires numeric confidence")
        if not isinstance(reasons, list) or not all(isinstance(item, str) for item in reasons):
            raise ValueError("model-backed selector response reasons must be a list of strings")

        allowed = set(candidate_ids)
        unknown = tuple(agent_id for agent_id in selected if agent_id not in allowed)
        if unknown:
            raise ValueError(
                "model-backed selector returned Agent IDs outside the candidate set: "
                + ", ".join(unknown)
            )
        return SelectionDecision(
            selected_agents=tuple(selected),
            confidence=float(confidence),
            reasons=tuple(reasons),
        )

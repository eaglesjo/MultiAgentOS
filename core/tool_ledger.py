"""Durable append-only tool invocation ledger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from core.contracts.replay import ReplayDisposition, ReplayPolicy
from core.contracts.tool_ledger import ToolInvocationRecord, ToolInvocationState
from core.security import redact_sensitive


class ToolInvocationStore:
    """Persist invocation state transitions independently of runtime events."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for_work_unit(self, work_unit_id: str) -> Path:
        """Return a ledger path contained by the configured root."""
        if (
            not isinstance(work_unit_id, str)
            or not work_unit_id.strip()
            or work_unit_id in {".", ".."}
            or any(char in work_unit_id for char in ("/", "\\", ":", "\\x00"))
        ):
            raise ValueError("invalid tool ledger work_unit_id")
        root = self.root.resolve()
        path = (root / f"{work_unit_id}.jsonl").resolve()
        if path.parent != root:
            raise ValueError("tool ledger path escapes configured root")
        return path

    def append(self, record: ToolInvocationRecord) -> Path:
        if not record.work_unit_id:
            raise ValueError("tool invocation requires work_unit_id")
        path = self._path_for_work_unit(record.work_unit_id)
        payload = {
            "invocation_id": record.invocation_id,
            "work_unit_id": record.work_unit_id,
            "tool_id": record.tool_id,
            "call_id": record.call_id,
            "arguments": redact_sensitive(record.arguments),
            "state": record.state.value,
            "replay_policy": {
                "disposition": record.replay_policy.disposition.value,
                "reason": record.replay_policy.reason,
                "idempotency_key": record.replay_policy.idempotency_key,
            },
            "sequence": record.sequence,
            "result_reference": record.result_reference,
            "error": redact_sensitive(record.error),
            "idempotency_key": record.idempotency_key,
            "decision_id": record.decision_id,
            "agent_id": record.agent_id,
            "model_id": record.model_id,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        return path

    def load(self, work_unit_id: str) -> tuple[ToolInvocationRecord, ...]:
        path = self._path_for_work_unit(work_unit_id)
        if not path.exists():
            return ()
        latest: dict[str, ToolInvocationRecord] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            policy = raw["replay_policy"]
            record = ToolInvocationRecord(
                invocation_id=raw["invocation_id"],
                work_unit_id=raw["work_unit_id"],
                tool_id=raw["tool_id"],
                arguments=dict(raw.get("arguments", {})),
                call_id=raw.get("call_id"),
                state=ToolInvocationState(raw["state"]),
                replay_policy=ReplayPolicy(
                    ReplayDisposition(policy["disposition"]),
                    reason=str(policy.get("reason", "")),
                    idempotency_key=policy.get("idempotency_key"),
                ),
                sequence=int(raw["sequence"]),
                result_reference=raw.get("result_reference"),
                error=raw.get("error"),
                idempotency_key=raw.get("idempotency_key"),
                decision_id=raw.get("decision_id"),
                agent_id=raw.get("agent_id"),
                model_id=raw.get("model_id"),
            )
            latest[record.invocation_id] = record
        return tuple(sorted(latest.values(), key=lambda item: item.sequence))

    def find_by_idempotency_key(
        self, work_unit_id: str, idempotency_key: str
    ) -> tuple[ToolInvocationRecord, ...]:
        """Return durable invocation records using the same idempotency key."""
        if not idempotency_key:
            return ()
        return tuple(
            record
            for record in self.load(work_unit_id)
            if record.idempotency_key == idempotency_key
        )

    def unresolved(self, work_unit_id: str) -> tuple[ToolInvocationRecord, ...]:
        return tuple(
            record
            for record in self.load(work_unit_id)
            if record.state
            in {
                ToolInvocationState.REQUESTED,
                ToolInvocationState.STARTED,
                ToolInvocationState.UNKNOWN,
            }
        )

    def next_sequence(self, work_unit_id: str) -> int:
        records = self.load(work_unit_id)
        return records[-1].sequence + 1 if records else 1

    def has_unresolved(self, work_unit_id: str) -> bool:
        return bool(self.unresolved(work_unit_id))

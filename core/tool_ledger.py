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

    def append(self, record: ToolInvocationRecord) -> Path:
        if not record.work_unit_id:
            raise ValueError("tool invocation requires work_unit_id")
        path = self.root / f"{record.work_unit_id}.jsonl"
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
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        return path

    def load(self, work_unit_id: str) -> tuple[ToolInvocationRecord, ...]:
        path = self.root / f"{work_unit_id}.jsonl"
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
            )
            latest[record.invocation_id] = record
        return tuple(sorted(latest.values(), key=lambda item: item.sequence))

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

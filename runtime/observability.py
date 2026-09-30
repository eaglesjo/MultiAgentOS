"""Durable read-only execution observability."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.execution_state import ExecutionStateStore
from core.recovery_audit import RecoveryAuditStore
from core.state import RuntimeEventStore, WorkStateStore
from core.tool_ledger import ToolInvocationStore
from core.contracts.work_unit import WorkStatus


@dataclass(frozen=True)
class ExecutionEvidenceSummary:
    work_unit_id: str
    work_status: str
    execution_state: str
    event_count: int
    tool_count: int
    unresolved_tool_count: int
    message_count: int
    checkpoint_status: str | None
    recovery_decision: str | None
    model_ids: tuple[str, ...]
    timeline: tuple[dict[str, Any], ...]


class ExecutionObservability:
    """Project-scoped read-only summary over durable execution evidence."""

    def __init__(self, project_root: Path) -> None:
        root = Path(project_root).resolve()
        durable = root / ".multiagentos"
        self.work_store = WorkStateStore(durable / "work")
        self.events = RuntimeEventStore(durable / "events")
        self.ledger = ToolInvocationStore(durable / "tool-ledger")
        self.execution_state = ExecutionStateStore(durable / "execution-state")
        self.recovery = RecoveryAuditStore(durable / "recovery")

    def summarize(self, work_unit_id: str, *, timeline_limit: int = 20) -> ExecutionEvidenceSummary:
        if timeline_limit < 1:
            raise ValueError("timeline_limit must be at least 1")

        work_unit = self.work_store.load(work_unit_id)
        events = self.events.load(work_unit_id)
        tools = self.ledger.load(work_unit_id)
        unresolved = self.ledger.unresolved(work_unit_id)
        messages = self.execution_state.load_messages(work_unit_id)
        try:
            checkpoint = self.execution_state.load_stream_checkpoint(work_unit_id)
            checkpoint_status = checkpoint.status.value
        except FileNotFoundError:
            checkpoint_status = None
        recovery_records = self.recovery.load(work_unit_id)
        recovery_decision = (
            str(recovery_records[-1].get("disposition"))
            if recovery_records else None
        )

        model_ids: list[str] = []
        for message in messages:
            metadata = message.get("metadata")
            if isinstance(metadata, dict):
                model_id = metadata.get("model_id")
                if isinstance(model_id, str) and model_id not in model_ids:
                    model_ids.append(model_id)

        timeline = tuple(
            {
                "sequence": event.get("sequence"),
                "kind": event.get("kind"),
            }
            for event in events[-timeline_limit:]
        )

        execution_state = "not_started"
        if events:
            last = str(events[-1].get("kind"))
            if last == "completed":
                execution_state = "completed"
            elif unresolved:
                execution_state = "tool_in_flight"
            elif checkpoint_status == "interrupted":
                execution_state = "interrupted"
            elif work_unit.status is WorkStatus.FAILED:
                execution_state = "failed"
            else:
                execution_state = "executing"

        return ExecutionEvidenceSummary(
            work_unit_id=work_unit_id,
            work_status=work_unit.status.value,
            execution_state=execution_state,
            event_count=len(events),
            tool_count=len(tools),
            unresolved_tool_count=len(unresolved),
            message_count=len(messages),
            checkpoint_status=checkpoint_status,
            recovery_decision=recovery_decision,
            model_ids=tuple(model_ids),
            timeline=timeline,
        )

    def as_dict(self, work_unit_id: str, *, timeline_limit: int = 20) -> dict[str, Any]:
        summary = self.summarize(work_unit_id, timeline_limit=timeline_limit)
        return {
            "work_unit_id": summary.work_unit_id,
            "work_status": summary.work_status,
            "execution_state": summary.execution_state,
            "event_count": summary.event_count,
            "tool_count": summary.tool_count,
            "unresolved_tool_count": summary.unresolved_tool_count,
            "message_count": summary.message_count,
            "checkpoint_status": summary.checkpoint_status,
            "recovery_decision": summary.recovery_decision,
            "model_ids": summary.model_ids,
            "timeline": summary.timeline,
        }

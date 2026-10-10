"""Append-only recovery decision audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from core.contracts.recovery import RecoveryPlan
from core.state_paths import state_file_path


class RecoveryAuditStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        plan: RecoveryPlan,
        *,
        source_identity: dict[str, object] | None = None,
    ) -> Path:
        path = state_file_path(self.root, plan.work_unit_id, ".jsonl")
        payload = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "work_unit_id": plan.work_unit_id,
            "disposition": plan.disposition.value,
            "pending_tool_call_ids": list(plan.pending_tool_call_ids),
            "safe_to_resume": plan.safe_to_resume,
            "reason": plan.reason,
            "source_identity": source_identity,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        return path

    def load(self, work_unit_id: str) -> tuple[dict[str, object], ...]:
        path = state_file_path(self.root, work_unit_id, ".jsonl")
        if not path.exists():
            return ()
        return tuple(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

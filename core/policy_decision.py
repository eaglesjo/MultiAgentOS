"""Append-only, redacted policy decision evidence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from core.contracts.policy_decision import PolicyDecision
from core.security import redact_sensitive
from core.state_paths import state_file_path


class PolicyDecisionStore:
    """Persist one durable decision journal per WorkUnit."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def append(self, decision: PolicyDecision) -> Path:
        path = state_file_path(self.root, decision.work_unit_id, ".jsonl")
        payload = redact_sensitive({
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "work_unit_id": decision.work_unit_id,
            "category": decision.category.value,
            "disposition": decision.disposition.value,
            "reason": decision.reason,
            "action": decision.action,
            "session_id": decision.session_id,
            "metadata": dict(decision.metadata or {}),
        })
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

    def recent(self, work_unit_id: str, *, limit: int = 20) -> tuple[dict[str, object], ...]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        return self.load(work_unit_id)[-limit:]

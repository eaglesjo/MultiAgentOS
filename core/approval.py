"""Durable, redacted approval evidence."""

from __future__ import annotations

import json
from pathlib import Path

from core.contracts.approval import ApprovalGrant, ApprovalDecision
from core.security import redact_sensitive


class ApprovalStore:
    """Persist approval decisions without prompts, credentials, or raw arguments."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, grant: ApprovalGrant, *, metadata: dict[str, object] | None = None) -> Path:
        path = self.root / f"{grant.approval_id}.json"
        payload = redact_sensitive({
            "approval_id": grant.approval_id,
            "decision": grant.decision.value,
            "action": grant.action,
            "work_unit_id": grant.work_unit_id,
            "session_id": grant.session_id,
            "expires_at": grant.expires_at,
            "reason": grant.reason,
            "metadata": dict(metadata or {}),
        })
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def load(self, approval_id: str) -> ApprovalGrant:
        data = json.loads((self.root / f"{approval_id}.json").read_text(encoding="utf-8"))
        return ApprovalGrant(
            approval_id=str(data["approval_id"]),
            decision=ApprovalDecision(str(data["decision"])),
            action=str(data["action"]),
            work_unit_id=data.get("work_unit_id"),
            session_id=data.get("session_id"),
            expires_at=data.get("expires_at"),
            reason=str(data.get("reason", "")),
        )

"""Project-scoped deterministic execution limit store."""

from __future__ import annotations

import json
import time
from pathlib import Path

from core.contracts.execution_limits import ExecutionBudget, LimitDecision, LimitDisposition, RateLimit
from core.security import redact_sensitive


class ExecutionLimitStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, work_unit_id: str) -> Path:
        return self.root / f"{work_unit_id}.json"

    def _load(self, work_unit_id: str) -> dict[str, object]:
        path = self._path(work_unit_id)
        if not path.exists():
            return {"tool_calls": 0, "rounds": 0, "usage_units": 0, "rate_windows": {}}
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, work_unit_id: str, state: dict[str, object]) -> None:
        self._path(work_unit_id).write_text(
            json.dumps(redact_sensitive(state), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def check_tool_call(
        self,
        work_unit_id: str,
        *,
        budget: ExecutionBudget,
        rate_limit: RateLimit | None = None,
        now: float | None = None,
    ) -> LimitDecision:
        state = self._load(work_unit_id)
        calls = int(state.get("tool_calls", 0))
        if budget.max_tool_calls is not None and calls >= budget.max_tool_calls:
            return LimitDecision(LimitDisposition.DENY, "tool call budget exhausted", 0)
        if rate_limit is not None:
            current = now if now is not None else time.time()
            window = int(current // rate_limit.window_seconds)
            windows = dict(state.get("rate_windows", {}))
            used = int(windows.get(str(window), 0))
            if used >= rate_limit.max_calls:
                return LimitDecision(LimitDisposition.DENY, "tool call rate limit exhausted", 0)
            return LimitDecision(LimitDisposition.ALLOW, "allowed", min(
                budget.max_tool_calls - calls - 1 if budget.max_tool_calls is not None else rate_limit.max_calls - used - 1,
                rate_limit.max_calls - used - 1,
            ))
        return LimitDecision(
            LimitDisposition.ALLOW,
            "allowed",
            budget.max_tool_calls - calls - 1 if budget.max_tool_calls is not None else None,
        )

    def record_tool_call(self, work_unit_id: str, *, now: float | None = None, rate_limit: RateLimit | None = None) -> None:
        state = self._load(work_unit_id)
        state["tool_calls"] = int(state.get("tool_calls", 0)) + 1
        if rate_limit is not None:
            current = now if now is not None else time.time()
            window = int(current // rate_limit.window_seconds)
            windows = dict(state.get("rate_windows", {}))
            windows[str(window)] = int(windows.get(str(window), 0)) + 1
            state["rate_windows"] = windows
        self._save(work_unit_id, state)

    def record_round(self, work_unit_id: str) -> None:
        state = self._load(work_unit_id)
        state["rounds"] = int(state.get("rounds", 0)) + 1
        self._save(work_unit_id, state)

    def check_round(self, work_unit_id: str, *, budget: ExecutionBudget) -> LimitDecision:
        state = self._load(work_unit_id)
        rounds = int(state.get("rounds", 0))
        if budget.max_rounds is not None and rounds >= budget.max_rounds:
            return LimitDecision(LimitDisposition.DENY, "round budget exhausted", 0)
        return LimitDecision(
            LimitDisposition.ALLOW,
            "allowed",
            budget.max_rounds - rounds - 1 if budget.max_rounds is not None else None,
        )

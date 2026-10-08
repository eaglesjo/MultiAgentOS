"""Deterministic execution-route selection for Agent WorkUnits."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExecutionRoute(StrEnum):
    LOCAL = "local"
    GITHUB_ACTIONS = "github_actions"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ExecutionRouteDecision:
    route: ExecutionRoute
    reason: str
    requires_explicit_github_permission: bool = False


def select_execution_route(
    *,
    local_available: bool = True,
    local_failed: bool = False,
    force_remote: bool = False,
    allow_github_actions: bool = False,
    prefer_local: bool = True,
) -> ExecutionRouteDecision:
    """Choose local execution first and remote Actions only as a bounded fallback."""

    if force_remote:
        if allow_github_actions:
            return ExecutionRouteDecision(
                ExecutionRoute.GITHUB_ACTIONS,
                "remote execution was explicitly requested",
            )
        return ExecutionRouteDecision(
            ExecutionRoute.BLOCKED,
            "remote execution was explicitly requested but GitHub Actions is disabled",
            True,
        )

    if prefer_local and local_available and not local_failed:
        return ExecutionRouteDecision(
            ExecutionRoute.LOCAL,
            "local execution is available and has not failed",
        )

    if allow_github_actions:
        reason = (
            "local execution failed; bounded GitHub Actions fallback is permitted"
            if local_failed
            else "local execution is unavailable; bounded GitHub Actions fallback is permitted"
        )
        return ExecutionRouteDecision(
            ExecutionRoute.GITHUB_ACTIONS,
            reason,
        )

    if local_available:
        return ExecutionRouteDecision(
            ExecutionRoute.LOCAL,
            "GitHub Actions is disabled; retain local execution",
        )

    return ExecutionRouteDecision(
        ExecutionRoute.BLOCKED,
        "no permitted execution route is available",
        True,
    )

"""Agent-plan reconciliation for evolving workspace-aware projects."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from agents.catalog import build_agent_catalog
from profiles.agent_plan import AgentPlan
from profiles.workspace import WorkspaceAnalysis


@dataclass(frozen=True)
class AgentPlanReconciliation:
    current: tuple[str, ...]
    desired: tuple[str, ...]
    to_add: tuple[str, ...]
    to_remove: tuple[str, ...]
    unchanged: tuple[str, ...]
    requires_approval: bool
    workspaces: tuple[str, ...]


def _current_agents(root: Path) -> tuple[str, ...]:
    path = root / ".multiagentos" / "agents.json"
    if not path.is_file():
        return ()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    return tuple(sorted(
        item["id"] for item in data.get("agents", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ))


def build_reconciliation(root: Path, plan: AgentPlan, analyses: tuple[WorkspaceAnalysis, ...]) -> AgentPlanReconciliation:
    current = _current_agents(root)
    desired = tuple(sorted(plan.selected))
    current_set, desired_set = set(current), set(desired)
    return AgentPlanReconciliation(
        current=current,
        desired=desired,
        to_add=tuple(sorted(desired_set - current_set)),
        to_remove=tuple(sorted(current_set - desired_set)),
        unchanged=tuple(sorted(current_set & desired_set)),
        requires_approval=plan.requires_approval,
        workspaces=tuple(analysis.spec.id for analysis in analyses),
    )


def apply_reconciliation(
    root: Path,
    plan: AgentPlan,
    analyses: tuple[WorkspaceAnalysis, ...],
    *,
    approved: bool = False,
) -> AgentPlanReconciliation:
    reconciliation = build_reconciliation(root, plan, analyses)
    if reconciliation.requires_approval and not approved:
        raise PermissionError(
            "workspace agent-plan reconciliation requires approval; "
            "run detect, review the workspace plans, then rerun reconcile with --approve"
        )

    target = root / ".multiagentos"
    target.mkdir(parents=True, exist_ok=True)
    agents = tuple(
        agent for agent in build_agent_catalog(plan.profiles)
        if agent.id in plan.selected
    )
    (target / "agents.json").write_text(
        json.dumps(
            {"version": 1, "agents": [
                {
                    "id": agent.id,
                    "role": agent.role,
                    "kind": agent.kind,
                    "capabilities": sorted(agent.capabilities),
                    "tools": sorted(agent.tools),
                    "permissions": sorted(agent.permissions),
                    "models": list(agent.model_ids),
                }
                for agent in agents
            ]},
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    profile_path = target / "profile.json"
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        profile = {}
    profile["version"] = 1
    profile["workspace_plans"] = [
        {
            "id": analysis.spec.id,
            "kind": analysis.spec.kind,
            "path": str(analysis.spec.path),
            "evidence": list(analysis.spec.evidence),
            "detections": [
                {"id": result.profile_id, "confidence": result.confidence, "evidence": list(result.evidence)}
                for result in analysis.detections
            ],
        }
        for analysis in analyses
    ]
    profile["agent_plan"] = {
        "selected": list(plan.selected),
        "excluded": list(plan.excluded),
        "requires_approval": plan.requires_approval,
        "approved": approved,
        "rationale": list(plan.rationale),
    }
    profile_path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    (target / "reconciliation.json").write_text(
        json.dumps(
            {
                "current": list(reconciliation.current),
                "desired": list(reconciliation.desired),
                "to_add": list(reconciliation.to_add),
                "to_remove": list(reconciliation.to_remove),
                "unchanged": list(reconciliation.unchanged),
                "workspaces": list(reconciliation.workspaces),
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return reconciliation

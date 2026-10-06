"""CLI entry point for one bounded GitHub Actions execution mission."""

from __future__ import annotations

import argparse
import json
import uuid

from core.contracts.execution_mission import ExecutionMission, MissionOperation
from integrations.github.gateway import GitHubGatewayClient
from runtime.github_actions import GitHubActionsMissionRuntime
from runtime.policy import ExecutionPolicy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run and verify one bounded GitHub Actions mission."
    )
    parser.add_argument("--repository", required=True, help="owner/name")
    parser.add_argument("--operation", choices=[item.value for item in MissionOperation], default="test")
    parser.add_argument("--workflow", default="execution-mission.yml")
    parser.add_argument("--ref", default="main", help="workflow ref used to dispatch the workflow")
    parser.add_argument(
        "--source-sha",
        help="exact 40-character commit SHA to execute; defaults to the ref tip",
    )
    parser.add_argument("--mission-id", default=None)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument(
        "--allow-github-actions",
        action="store_true",
        help="explicitly permit remote GitHub Actions execution",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    gateway = GitHubGatewayClient()

    if not args.allow_github_actions:
        raise SystemExit(
            "remote execution is disabled by default; "
            "re-run with --allow-github-actions"
        )

    source_sha = args.source_sha or gateway.get_branch(args.repository, args.ref).sha
    mission = ExecutionMission(
        id=args.mission_id or f"mission-{uuid.uuid4().hex}",
        repository=args.repository,
        source_sha=source_sha,
        workflow=args.workflow,
        operation=MissionOperation(args.operation),
        ref=args.ref,
        expected_artifacts=("execution-mission-evidence",),
    )
    runtime = GitHubActionsMissionRuntime(
        gateway,
        ExecutionPolicy(allow_github_actions=True),
        poll_interval_seconds=args.poll_interval,
        timeout_seconds=args.timeout,
    )
    result = runtime.run(mission)
    print(
        json.dumps(
            {
                "mission_id": result.evidence.mission_id,
                "run_id": result.evidence.run_id,
                "status": result.evidence.status,
                "conclusion": result.evidence.conclusion,
                "source_sha": result.evidence.source_sha,
                "head_sha": result.evidence.head_sha,
                "url": result.evidence.url,
                "artifacts": list(result.evidence.artifacts),
                "logs_available": result.evidence.logs_available,
                "disposition": result.evidence.disposition.value,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

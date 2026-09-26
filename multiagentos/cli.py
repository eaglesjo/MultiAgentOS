"""Command-line entry point for VYRELON project bootstrap and execution."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from core.contracts.work_unit import WorkStatus, WorkUnit
from installer.init import ProjectInitializer
from profiles.detector import ProfileDetector
from runtime.github_probe import probe
from runtime.process import ProcessRuntime


def _work_state(root: Path):
    from runtime.vyrelon import VYRELONRuntime

    return VYRELONRuntime().state_store(root)


def _run_process(root: Path, work: WorkUnit, command: list[str]) -> int:
    store = _work_state(root)
    work.metadata["command"] = command
    if work.status == WorkStatus.FAILED:
        work.status = WorkStatus.EXECUTING
    elif work.status != WorkStatus.EXECUTING:
        work.transition(WorkStatus.EXECUTING)
    store.save(work)

    try:
        result = ProcessRuntime().run(command, cwd=str(root))
        work.metadata["returncode"] = result.returncode
        work.metadata["stdout"] = result.stdout
        work.metadata["stderr"] = result.stderr
        if result.returncode == 0:
            work.transition(WorkStatus.COMPLETED)
            store.save(work)
            print(result.stdout, end="")
            return 0

        work.transition(WorkStatus.FAILED)
        store.save(work)
        print(result.stdout, end="")
        print(result.stderr, end="")
        return result.returncode
    except Exception as exc:
        work.metadata["error"] = str(exc)
        if work.status not in {WorkStatus.FAILED, WorkStatus.COMPLETED}:
            work.transition(WorkStatus.FAILED)
        store.save(work)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="multiagentos")
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect = subparsers.add_parser("detect", help="detect technology profiles")
    detect.add_argument("path", nargs="?", default=".")

    init = subparsers.add_parser("init", help="initialize VYRELON in a project")
    init.add_argument("path", nargs="?", default=".")

    run = subparsers.add_parser("run", help="create and execute a persistent WorkUnit")
    run.add_argument("path", nargs="?", default=".")
    run.add_argument("--objective", required=True)
    run.add_argument("--id", dest="work_unit_id")
    run.add_argument("--command", dest="process_command", nargs="+", required=True)

    resume = subparsers.add_parser("resume", help="resume a persisted WorkUnit")
    resume.add_argument("work_unit_id")
    resume.add_argument("path", nargs="?", default=".")

    status = subparsers.add_parser("status", help="show a persisted WorkUnit")
    status.add_argument("work_unit_id")
    status.add_argument("path", nargs="?", default=".")

    github = subparsers.add_parser("github", help="use VYRELON GitHub runtime")
    github_sub = github.add_subparsers(dest="github_command", required=True)
    probe_parser = github_sub.add_parser("probe", help="verify GitHub access for a repository")
    probe_parser.add_argument("repository")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "github" and args.github_command == "probe":
        print(json.dumps(probe(args.repository), indent=2))
        return 0

    root = Path(args.path).expanduser().resolve()

    if args.command == "run":
        work = WorkUnit(
            id=args.work_unit_id or uuid.uuid4().hex,
            objective=args.objective,
        )
        print(f"WorkUnit: {work.id}")
        return _run_process(root, work, args.process_command)

    if args.command == "resume":
        work = _work_state(root).load(args.work_unit_id)
        if work.status not in {WorkStatus.EXECUTING, WorkStatus.FAILED}:
            raise ValueError(
                f"WorkUnit {work.id} is not resumable from status {work.status.value}"
            )
        command = list(work.metadata.get("command", []))
        if not command:
            raise ValueError(f"WorkUnit {work.id} has no persisted command")
        return _run_process(root, work, command)

    if args.command == "status":
        work = _work_state(root).load(args.work_unit_id)
        print(
            json.dumps(
                {
                    "id": work.id,
                    "objective": work.objective,
                    "status": work.status.value,
                    "assigned_agents": work.assigned_agents,
                    "metadata": work.metadata,
                },
                indent=2,
            )
        )
        return 0

    detector = ProfileDetector()
    detections = detector.detect(root)

    if args.command == "detect":
        print(
            json.dumps(
                [
                    {
                        "profile": result.profile_id,
                        "confidence": result.confidence,
                        "evidence": list(result.evidence),
                    }
                    for result in detections
                ],
                indent=2,
            )
        )
        return 0

    config = ProjectInitializer().apply(root, detections)
    print(f"Initialized VYRELON: {config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

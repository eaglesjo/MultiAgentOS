"""Command-line entry point for VYRELON project bootstrap."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from core.chat_agent_bridge import ChatAgentRequest
from core.contracts import WorkUnit
from installer.init import ProjectInitializer
from profiles.detector import ProfileDetector
from runtime.execution_config import load_execution_config
from runtime.execution_registry import resolve_execution_contracts
from runtime.github_probe import probe
from runtime.process import ProcessRuntime
from runtime.status import project_status
from runtime.vyrelon import VYRELONRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="multiagentos")
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect = subparsers.add_parser("detect", help="detect technology profiles")
    detect.add_argument("path", nargs="?", default=".")

    init = subparsers.add_parser("init", help="initialize VYRELON in a project")
    init.add_argument("path", nargs="?", default=".")
    init.add_argument(
        "--component",
        choices=("vyrelon", "multi-agent", "all"),
        default="all",
        help="install only VYRELON, only multi-agent, or both",
    )

    status = subparsers.add_parser("status", help="show VYRELON project and durable workflow state")
    status.add_argument("path", nargs="?", default=".")

    run = subparsers.add_parser("run", help="execute a local command through the VYRELON lifecycle")
    run.add_argument("--path", default=".")
    run.add_argument("--objective", required=True, help="WorkUnit objective")
    run.add_argument("--agent", help="override the project execution agent id")
    run.add_argument("--model", help="override the project execution model id")
    run.add_argument("exec_command", nargs=argparse.REMAINDER, help="command after --")

    resume = subparsers.add_parser("resume", help="resume a durable VYRELON orchestration checkpoint")
    resume.add_argument("work_unit_id")
    resume.add_argument("--path", default=".")
    resume.add_argument("--agent", help="override the project execution agent id")
    resume.add_argument("--model", help="override the project execution model id")

    chat = subparsers.add_parser("chat", help="send a request to the project's configured Chat Agent")
    chat.add_argument("--path", default=".")
    chat.add_argument("--objective", required=True, help="request for the Chat Agent")
    chat.add_argument("--agent", help="override the configured Chat Agent id")
    chat.add_argument("--model", help="override the configured Chat Agent model")
    chat.add_argument("--session", help="persist conversation turns in this session id")
    chat.add_argument("--execute", action="store_true", help="execute the explicit command after -- through VYRELON")
    chat.add_argument("exec_command", nargs=argparse.REMAINDER, help="explicit command after -- when using --execute")

    github = subparsers.add_parser("github", help="use VYRELON GitHub runtime")
    github_sub = github.add_subparsers(dest="github_command", required=True)
    probe_parser = github_sub.add_parser("probe", help="verify GitHub access for a repository")
    probe_parser.add_argument("repository")

    return parser


def _execution_contracts(root: Path, agent_override: str | None, model_override: str | None):
    config = load_execution_config(root)
    if config.runtime != "process":
        raise ValueError(f"unsupported CLI execution runtime: {config.runtime}")
    agent_id = agent_override or config.agent_id
    model_id = model_override or config.model_id
    agent, model = resolve_execution_contracts(agent_id, model_id)
    return config, agent, [model]


def _chat_request(root: Path, objective: str, session_id: str | None) -> ChatAgentRequest:
    inputs: dict[str, object] = {}
    if session_id:
        store = VYRELONRuntime().chat_session_store(root)
        try:
            session = store.load(session_id)
        except FileNotFoundError:
            session = None
        if session is not None:
            inputs["conversation"] = tuple(
                {"role": turn.get("role"), "content": turn.get("content")}
                for turn in session.turns
            )
    return ChatAgentRequest(objective=objective, inputs=inputs)


def _run_chat(
    root: Path,
    objective: str,
    agent_override: str | None,
    model_override: str | None,
    session_id: str | None,
    execute: bool = False,
    exec_command: list[str] | None = None,
) -> int:
    runtime = VYRELONRuntime()
    configured_agent, configured_model = runtime.project_chat_agent(root)
    agent_id = agent_override or configured_agent.id
    agent = runtime.chat_agent_registry().get(agent_id)
    model = model_override or (configured_model if agent_id == configured_agent.id else None)

    if agent_id == configured_agent.id and model == configured_model:
        _, adapter = runtime.project_chat_adapter(root)
    else:
        from runtime.chat_adapter_registry import resolve_project_chat_adapter
        adapter = resolve_project_chat_adapter(agent, model=model)

    session = None
    if session_id:
        store = runtime.chat_session_store(root)
        try:
            session = store.load(session_id)
        except FileNotFoundError:
            session = runtime.create_chat_session(session_id, chat_agent_id=agent.id)

    request = _chat_request(root, objective, session_id)

    if execute:
        command = list(exec_command or [])
        while command and command[0] == "--":
            command.pop(0)
        if not command:
            raise SystemExit("chat --execute requires an explicit command after --")
        config, execution_agent, models = _execution_contracts(root, None, model_override)

        class CommandExecutor:
            def execute(self, *, agent, model_id, work_unit):
                result = ProcessRuntime(runtime.policy).run(
                    list(work_unit.inputs["command"]), cwd=str(root)
                )
                work_unit.metadata["process_returncode"] = result.returncode
                work_unit.metadata["process_stdout"] = result.stdout
                work_unit.metadata["process_stderr"] = result.stderr
                if result.returncode != 0:
                    raise RuntimeError(f"command failed with exit code {result.returncode}")
                return result

        request = ChatAgentRequest(
            objective=objective,
            inputs={**(request.inputs or {}), "command": command},
            work_unit_id=request.work_unit_id,
        )
        result = runtime.execute_chat_request(
            request=request,
            adapter=adapter,
            agent=execution_agent,
            models=models,
            executor=CommandExecutor(),
            chat_agent_id=agent.id,
            preferred_model_ids=[models[0].id],
            session=session,
            project_root=root,
        )
        if session is not None:
            session.add_turn("user", objective)
            session.add_turn("assistant", result.chat_response.summary)
            session.metadata["last_plan_steps"] = [step.id for step in result.plan.steps]
            runtime.chat_session_store(root).save(session)
        print(json.dumps({
            "mode": "execute",
            "chat_agent_id": agent.id,
            "provider": agent.provider.value,
            "summary": result.chat_response.summary,
            "work_unit_id": result.work_unit.id,
            "status": result.work_unit.status.value,
            "execution_agent_id": execution_agent.id,
            "execution_model_id": result.orchestration.delegation.assignment.model_id,
            "execution_evidence": result.work_unit.metadata.get("execution_evidence", []),
            "verification_evidence": result.work_unit.metadata.get("verification_evidence", []),
            "review_evidence": result.work_unit.metadata.get("review_evidence", []),
            "session_id": session.id if session is not None else None,
        }, indent=2, ensure_ascii=False))
        return 0

    _, plan, response = runtime.chat_request(request, adapter, agent_id=agent.id)
    if session is None and session_id:
        session = runtime.create_chat_session(session_id, chat_agent_id=agent.id)
    if session is not None:
        session.add_turn("user", objective)
        session.add_turn("assistant", response.summary)
        session.metadata["last_plan_steps"] = [step.id for step in plan.steps]
        runtime.chat_session_store(root).save(session)

    print(json.dumps({
        "mode": "chat",
        "chat_agent_id": agent.id,
        "provider": agent.provider.value,
        "summary": response.summary,
        "steps": [
            {"id": step.id, "objective": step.objective, "agent_id": step.agent_id, "depends_on": list(step.depends_on)}
            for step in plan.steps
        ],
        "findings": list(response.findings),
        "artifacts": list(response.artifacts),
        "evidence": list(response.evidence),
        "session_id": session.id if session is not None else None,
    }, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "status":
        print(json.dumps(project_status(Path(args.path)), indent=2, ensure_ascii=False))
        return 0

    if args.command == "chat":
        root = Path(args.path).expanduser().resolve()
        return _run_chat(root, args.objective, args.agent, args.model, args.session, args.execute, args.exec_command)

    if args.command in {"run", "resume"}:
        root = Path(args.path).expanduser().resolve()
        runtime = VYRELONRuntime()
        config, agent, models = _execution_contracts(root, args.agent, args.model)

        class CommandExecutor:
            def __init__(self, process_runtime):
                self.process_runtime = process_runtime

            def execute(self, *, agent, model_id, work_unit):
                command = list(work_unit.inputs.get("command", []))
                if not command:
                    raise ValueError("WorkUnit has no persisted command")
                result = self.process_runtime.run(command, cwd=str(root))
                work_unit.metadata["process_returncode"] = result.returncode
                work_unit.metadata["process_stdout"] = result.stdout
                work_unit.metadata["process_stderr"] = result.stderr
                work_unit.metadata["execution_agent_id"] = agent.id
                work_unit.metadata["execution_model_id"] = model_id
                if result.returncode != 0:
                    raise RuntimeError(f"command failed with exit code {result.returncode}")
                return result

        executor = CommandExecutor(ProcessRuntime(runtime.policy))
        if args.command == "run":
            command = list(args.exec_command)
            while command and command[0] == "--":
                command.pop(0)
            if not command:
                raise SystemExit("run requires a command after --")
            work_unit = WorkUnit(
                id=uuid4().hex,
                objective=args.objective,
                inputs={"command": command},
                metadata={
                    "execution_runtime": config.runtime,
                    "execution_agent_id": agent.id,
                    "execution_model_id": models[0].id,
                },
            )
            result = runtime.run(work_unit, agent, models, executor, project_root=root)
        else:
            result = runtime.resume_workflow(args.work_unit_id, agent, models, executor, project_root=root)
        print(json.dumps({
            "work_unit_id": result.work_unit.id,
            "status": result.work_unit.status.value,
            "objective": result.work_unit.objective,
            "artifacts": list(result.work_unit.artifacts),
        }, indent=2, ensure_ascii=False))
        return 0

    if args.command == "github" and args.github_command == "probe":
        print(json.dumps(probe(args.repository), indent=2))
        return 0

    root = Path(args.path).expanduser().resolve()
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

    config = ProjectInitializer().apply(root, detections, component=args.component)
    print(f"Initialized VYRELON: {config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

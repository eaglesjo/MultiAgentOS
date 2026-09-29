"""Command-line entry point for VYRELON project bootstrap and execution."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.work_unit import WorkStatus, WorkUnit
from runtime.execution_registry import resolve_execution_contracts
from runtime.execution_config import load_execution_config
from core.chat_agent_bridge import ChatAgentRequest
from installer.init import ProjectInitializer
from profiles.detector import ProfileDetector
from runtime.github_probe import probe
from runtime.process import ProcessRuntime
from runtime.status import project_status
from runtime import AgentExecutionRuntime
from runtime.agent.process import ProcessAgentExecutor


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
        store = AgentExecutionRuntime().chat_session_store(root)
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


def _work_state(root: Path):
    from runtime.vyrelon import VYRELONRuntime

    return VYRELONRuntime().state_store(root)


def _provider_runtime(root: Path):
    from runtime.vyrelon import VYRELONRuntime

    runtime = VYRELONRuntime()
    runtime.load_project_provider_config(root)
    return runtime


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

    profile = subparsers.add_parser("profile", help="show resolved VYRELON project/agent profiles")
    profile.add_argument("path", nargs="?", default=".")

    init = subparsers.add_parser("init", help="initialize VYRELON in a project")
    init.add_argument("path", nargs="?", default=".")
    init.add_argument("--component", choices=("vyrelon", "multi-agent", "all"), default="all")

    providers = subparsers.add_parser(
        "providers", help="inspect configured AI providers and models"
    )
    provider_sub = providers.add_subparsers(dest="providers_command", required=True)
    providers_list = provider_sub.add_parser("list", help="list configured providers/models")
    providers_list.add_argument("path", nargs="?", default=".")
    providers_validate = provider_sub.add_parser(
        "validate", help="validate provider configuration and environment credentials"
    )
    providers_validate.add_argument("path", nargs="?", default=".")

    models = subparsers.add_parser("models", help="execute configured AI models")
    model_sub = models.add_subparsers(dest="models_command", required=True)
    models_quota = model_sub.add_parser("quota", help="show observed and estimated model quota")
    models_quota.add_argument("path", nargs="?", default=".")
    models_health = model_sub.add_parser("health", help="show model health and cooldown state")
    models_health.add_argument("path", nargs="?", default=".")
    models_capabilities = model_sub.add_parser("capabilities", help="show normalized model capabilities")
    models_capabilities.add_argument("path", nargs="?", default=".")
    models_discover = model_sub.add_parser("discover", help="refresh provider model capabilities and quota")
    models_discover.add_argument("path", nargs="?", default=".")
    models_discover.add_argument("--no-refresh", action="store_true")
    models_control = model_sub.add_parser("control", help="show unified model control-plane state")
    models_control.add_argument("path", nargs="?", default=".")
    models_control.add_argument("--events", action="store_true", help="include recent control-plane events")
    models_explain = model_sub.add_parser("explain", help="explain model routing eligibility and selection")
    models_explain.add_argument("path", nargs="?", default=".")
    models_explain.add_argument("--agent", default="executor")
    models_explain.add_argument("--model", action="append", dest="preferred_models", default=None)
    models_explain.add_argument("--strategy", choices=("explicit", "pool", "auto"), default="pool")

    models_run = model_sub.add_parser("run", help="run a configured model through VYRELON")
    models_run.add_argument("path", nargs="?", default=".")
    models_run.add_argument("--model", required=True)
    models_run.add_argument("--objective", required=True)
    models_run.add_argument("--agent", default="executor")
    models_run.add_argument("--apply-changes", action="store_true")
    models_run.add_argument("--validate", action="append", default=[])
    models_run.add_argument("--mcp", action="append", default=[])

    run = subparsers.add_parser("run", help="create and execute a persistent WorkUnit")
    run.add_argument("path_arg", nargs="?", default=None)
    run.add_argument("--path", dest="path", default=None)
    run.add_argument("--objective", required=True)
    run.add_argument("--agent", default="executor")
    run.add_argument("--id", dest="work_unit_id")
    run.add_argument("--model", help="pin a model; omit to route automatically")
    run.add_argument("--apply-changes", action="store_true")
    run.add_argument("--validate", action="append", default=[])
    run.add_argument("--mcp", action="append", default=[])
    run.add_argument("--command", dest="process_command", nargs=argparse.REMAINDER)

    resume = subparsers.add_parser("resume", help="resume a persisted WorkUnit")
    resume.add_argument("work_unit_id")
    resume.add_argument("path_arg", nargs="?", default=None)
    resume.add_argument("--path", dest="path", default=None)

    status = subparsers.add_parser("status", help="show project state or a persisted WorkUnit")
    status.add_argument("target", nargs="?", default=".")
    status.add_argument("path", nargs="?", default=None)



    chat = subparsers.add_parser("chat", help="send a request to the project's configured Chat Agent")
    chat.add_argument("--path", default=".")
    chat.add_argument("--objective", required=True, help="request for the Chat Agent")
    chat.add_argument("--agent", help="override the configured Chat Agent id")
    chat.add_argument("--model", help="override the configured Chat Agent model")
    chat.add_argument("--session", help="persist conversation turns in this session id")
    chat.add_argument("--execute", action="store_true", help="execute the explicit command after -- through VYRELON")
    chat.add_argument("exec_command", nargs=argparse.REMAINDER, help="explicit command after -- when using --execute")

    mcp = subparsers.add_parser("mcp", help="serve or inspect VYRELON MCP")
    mcp_sub = mcp.add_subparsers(dest="mcp_command", required=True)
    mcp_serve = mcp_sub.add_parser("serve", help="run VYRELON as a stdio MCP server")
    mcp_serve.add_argument("--path", default=".")
    mcp_serve.add_argument("--allow-write", action="store_true", help="expose filesystem write and patch tools")
    mcp_serve.add_argument("--allow-process", action="store_true", help="expose shell execution")

    github = subparsers.add_parser("github", help="use VYRELON GitHub runtime")
    github_sub = github.add_subparsers(dest="github_command", required=True)
    probe_parser = github_sub.add_parser(
        "probe", help="verify GitHub access for a repository"
    )
    probe_parser.add_argument("repository")

    return parser


def _provider_list(root: Path) -> int:
    runtime = _provider_runtime(root)
    payload = [
        {
            "id": provider.id,
            "kind": provider.kind,
            "models": [
                {
                    "id": model.id,
                    "capabilities": sorted(model.capabilities),
                    "adapter_id": model.metadata.get("adapter_id"),
                }
                for model in provider.models
            ],
        }
        for provider in runtime.providers.providers()
    ]
    print(json.dumps(payload, indent=2))
    return 0



def _model_quota(root: Path) -> int:
    runtime = _provider_runtime(root)
    store = runtime.quota_store(root)
    payload = []
    for model in runtime.configured_models():
        if not store.exists(model.id):
            payload.append({
                "model": model.id,
                "provider": model.provider_id,
                "status": "unknown",
                "confidence": "unknown",
                "dimensions": {},
            })
            continue
        snapshot = store.load(model.id)
        payload.append({
            "model": snapshot.model_id,
            "provider": snapshot.provider_id,
            "scope": snapshot.scope,
            "observed_at": snapshot.observed_at.isoformat(),
            "confidence": snapshot.confidence.value,
            "dimensions": {
                item.name: {
                    "limit": item.limit,
                    "used": item.used,
                    "remaining": item.remaining,
                    "reset_at": item.reset_at.isoformat() if item.reset_at else None,
                    "confidence": item.confidence.value,
                    "source": item.source,
                }
                for item in snapshot.dimensions
            },
        })
    print(json.dumps(payload, indent=2))
    return 0

def _model_health(root: Path) -> int:
    runtime = _provider_runtime(root)
    registry = runtime.health_registry(root)
    payload = []
    for model in runtime.configured_models():
        health = registry.get(model.id)
        if health is None:
            payload.append({
                "model": model.id,
                "provider": model.provider_id,
                "status": "healthy",
                "available": True,
                "consecutive_failures": 0,
                "successes": 0,
            })
            continue
        payload.append({
            "model": health.model_id,
            "provider": health.provider_id,
            "status": health.status.value,
            "available": health.available,
            "consecutive_failures": health.consecutive_failures,
            "successes": health.successes,
            "last_error": health.last_error,
            "last_failure_at": health.last_failure_at.isoformat() if health.last_failure_at else None,
            "last_success_at": health.last_success_at.isoformat() if health.last_success_at else None,
            "cooldown_until": health.cooldown_until.isoformat() if health.cooldown_until else None,
        })
    print(json.dumps(payload, indent=2))
    return 0


def _model_capabilities(root: Path) -> int:
    runtime = _provider_runtime(root)
    registry = runtime.capability_registry(root)
    payload = []
    for model in runtime.configured_models():
        profile = registry.profile(model)
        payload.append({
            "model": profile.model_id,
            "provider": profile.provider_id,
            "capabilities": sorted(profile.capabilities),
            "confidence": profile.confidence.value,
            "source": profile.source,
        })
    print(json.dumps(payload, indent=2))
    return 0

def _model_control(root: Path, include_events: bool = False) -> int:
    runtime = _provider_runtime(root)
    control = runtime.model_control_plane(root)
    models = runtime.configured_models()
    payload = {
        "models": list(control.dashboard(models)),
    }
    if include_events:
        payload["events"] = list(control.events.recent())
    print(json.dumps(payload, indent=2, default=str))
    return 0


def _model_explain(root: Path, agent_id: str, preferred_models=None, strategy: str = "pool") -> int:
    runtime = _provider_runtime(root)
    explanation = runtime.explain_model_routing(
        root,
        agent_id=agent_id,
        preferred_model_ids=preferred_models,
        routing_strategy=strategy,
    )
    print(json.dumps({
        "agent": explanation.agent_id,
        "strategy": explanation.strategy.value,
        "selected_model": explanation.selected_model_id,
        "candidates": [
            {
                "model": candidate.model_id,
                "provider": candidate.provider_id,
                "selected": candidate.selected,
                "compatible": candidate.compatible,
                "health_available": candidate.health_available,
                "quota_available": candidate.quota_available,
                "capability_score": candidate.capability_score,
                "quota_score": candidate.quota_score,
                "missing_capabilities": sorted(candidate.missing_capabilities),
                "rejection_reasons": list(candidate.rejection_reasons),
            }
            for candidate in explanation.candidates
        ],
    }, indent=2, ensure_ascii=False))
    return 0


def _model_run(root: Path, model_id: str, objective: str, agent_id: str, *, apply_changes: bool = False, validation_commands: list[str] | None = None, mcp_server_ids: list[str] | None = None) -> int:
    from runtime.vyrelon import VYRELONRuntime

    runtime = _provider_runtime(root)
    if not runtime.providers.list_model_ids():
        raise ValueError("No configured models found")
    result = runtime.run_configured_work(
        root,
        objective=objective,
        agent_id=agent_id,
        preferred_model_ids=[model_id],
        apply_changes=apply_changes,
        validation_commands=tuple(validation_commands or ()),
        mcp_server_ids=tuple(mcp_server_ids or ()),
    )
    print(result.output.text, end="")
    return 0


def _provider_validate(root: Path) -> int:
    runtime = _provider_runtime(root)
    payload = []
    valid = True
    for model in runtime.configured_models():
        checks = runtime.credential_checks().get(model.id, ())
        missing = [check.environment_variable for check in checks if not check.present]
        if missing:
            valid = False
        payload.append(
            {
                "model": model.id,
                "provider": model.provider_id,
                "adapter_id": model.metadata.get("adapter_id"),
                "credential_environment_variables": [
                    {
                        "name": check.environment_variable,
                        "present": check.present,
                    }
                    for check in checks
                ],
                "valid": not missing,
            }
        )

    print(json.dumps({"valid": valid, "models": payload}, indent=2))
    return 0 if valid else 1


def main(argv: list[str] | None = None) -> int:
    if argv is not None:
        argv = list(argv)
        if argv and argv[0] == "run" and "--" in argv:
            argv[argv.index("--")] = "--command"
    args = build_parser().parse_args(argv)

    if args.command == "status":
        root = Path(args.path or args.target).expanduser().resolve()
        print(json.dumps(project_status(root), indent=2, ensure_ascii=False))
        return 0

    if args.command == "chat":
        root = Path(args.path).expanduser().resolve()
        return _run_chat(root, args.objective, args.agent, args.model, args.session, args.execute, args.exec_command)

    if args.command == "mcp" and args.mcp_command == "serve":
        from runtime.mcp.server import VYRELONMCPServer
        root = Path(args.path).expanduser().resolve()
        VYRELONMCPServer(
            root,
            allow_write=args.allow_write,
            allow_process=args.allow_process,
        ).serve_forever()
        return 0

    if args.command == "github" and args.github_command == "probe":
        print(json.dumps(probe(args.repository), indent=2))
        return 0

    if args.command == "profile":
        root = Path(args.path).expanduser().resolve()
        from runtime.vyrelon import VYRELONRuntime
        project, agents = VYRELONRuntime().profiles(root)
        print(
            json.dumps(
                {
                    "project": {
                        "id": project.id,
                        "root": project.root,
                        "technology_profiles": list(project.technology_profile_ids),
                        "agent_profiles": list(project.agent_profile_ids),
                        "metadata": project.metadata,
                    },
                    "agents": [
                        {
                            "id": agent.id,
                            "role": agent.role,
                            "profiles": list(agent.profile_ids),
                            "capabilities": sorted(agent.capabilities),
                            "tools": sorted(agent.tools),
                            "permissions": sorted(agent.permissions),
                            "model_ids": list(agent.model_ids),
                        }
                        for agent in agents
                    ],
                },
                indent=2,
            )
        )
        return 0

    if args.command == "providers":
        root = Path(args.path).expanduser().resolve()
        if args.providers_command == "list":
            return _provider_list(root)
        return _provider_validate(root)

    if args.command == "models":
        root = Path(args.path).expanduser().resolve()
        if args.models_command == "quota":
            return _model_quota(root)
        if args.models_command == "health":
            return _model_health(root)
        if args.models_command == "capabilities":
            return _model_capabilities(root)
        if args.models_command == "discover":
            runtime = _provider_runtime(root)
            print(json.dumps(list(runtime.discover_models(root, refresh=not args.no_refresh)), indent=2, default=str))
            return 0
        if args.models_command == "control":
            return _model_control(root, args.events)
        if args.models_command == "explain":
            return _model_explain(root, args.agent, args.preferred_models, args.strategy)
        if args.models_command == "run":
            return _model_run(
                root,
                args.model,
                args.objective,
                args.agent,
                apply_changes=args.apply_changes,
                validation_commands=args.validate,
                mcp_server_ids=args.mcp,
            )

    root = Path(getattr(args, "path", None) or getattr(args, "path_arg", None) or ".").expanduser().resolve()

    if args.command == "run":
        work = WorkUnit(
            id=args.work_unit_id or uuid.uuid4().hex,
            objective=args.objective,
        )
        agent = AgentContract(
            id=args.agent,
            role=args.agent,
            capabilities=frozenset({"execution"}),
            tools=frozenset({"process"}) if args.process_command else frozenset(),
        )
        print(f"WorkUnit: {work.id}")
        try:
            from runtime.vyrelon import VYRELONRuntime
            runtime = VYRELONRuntime()
            if not args.process_command:
                work.metadata["runtime"] = "configured-model"
                work.metadata["agent_id"] = args.agent
                if args.model:
                    work.metadata["model_id"] = args.model
                result = runtime.run_configured_work(
                    root,
                    objective=args.objective,
                    agent_id=args.agent,
                    work_unit_id=work.id,
                    preferred_model_ids=[args.model] if args.model else None,
                    apply_changes=args.apply_changes,
                    validation_commands=tuple(args.validate),
                    mcp_server_ids=tuple(args.mcp),
                )
                print(result.output.text, end="")
                return 0

            model = ModelSpec(
                id=args.model or "local-process",
                provider_id="vyrelon-local",
                capabilities=frozenset({"execution"}),
            )
            work.metadata["command"] = args.process_command
            work.metadata["runtime"] = "local-process"
            work.metadata["execution_agent_id"] = agent.id
            work.metadata["execution_model_id"] = model.id
            result = runtime.run_persistent(
                root,
                work,
                agent,
                [model],
                ProcessAgentExecutor(args.process_command),
                preferred_model_ids=[model.id],
            )
            if result.output.returncode == 0:
                print(result.output.stdout, end="")
                return 0
            print(result.output.stdout, end="")
            print(result.output.stderr, end="")
            return result.output.returncode
        except Exception as exc:
            print(str(exc))
            return 1

    if args.command == "resume":
        work = _work_state(root).load(args.work_unit_id)
        if work.status not in {WorkStatus.EXECUTING, WorkStatus.FAILED}:
            raise ValueError(
                f"WorkUnit {work.id} is not resumable from status {work.status.value}"
            )
        agent_id = str(work.metadata.get("agent_id", work.assigned_agents[-1] if work.assigned_agents else "executor"))
        from runtime.vyrelon import VYRELONRuntime
        runtime = VYRELONRuntime()
        if work.metadata.get("runtime") == "configured-model":
            model_id = str(work.metadata.get("model_id", ""))
            if not model_id:
                raise ValueError(f"WorkUnit {work.id} has no persisted model id")
            agent = AgentContract(
                id=agent_id,
                role=agent_id,
                capabilities=frozenset({"execution"}),
            )
            result = runtime.run_persistent_registered_model(
                root,
                work,
                agent,
                preferred_model_ids=[model_id],
            )
            print(result.output.text, end="")
            return 0

        command = list(work.metadata.get("command", []))
        if not command:
            raise ValueError(f"WorkUnit {work.id} has no persisted command")
        agent = AgentContract(
            id=agent_id,
            role=agent_id,
            capabilities=frozenset({"execution"}),
            tools=frozenset({"process"}),
        )
        model = ModelSpec(
            id="local-process",
            provider_id="vyrelon-local",
            capabilities=frozenset({"execution"}),
        )
        result = runtime.run_persistent(
            root,
            work,
            agent,
            [model],
            ProcessAgentExecutor(command),
            preferred_model_ids=["local-process"],
        )
        if result.output.returncode == 0:
            print(result.output.stdout, end="")
            return 0
        print(result.output.stdout, end="")
        print(result.output.stderr, end="")
        return result.output.returncode

    if args.command == "status":
        target = Path(args.target).expanduser().resolve() if args.path is None else Path(args.path).expanduser().resolve()
        if args.path is None and target.is_dir():
            print(json.dumps(project_status(target), indent=2, ensure_ascii=False))
            return 0
        work_id = args.target
        work = _work_state(target).load(work_id)
        print(json.dumps({"id": work.id, "objective": work.objective, "status": work.status.value, "assigned_agents": work.assigned_agents, "metadata": work.metadata}, indent=2))
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

    config = ProjectInitializer().apply(root, detections, component=args.component)
    print(f"Initialized VYRELON: {config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

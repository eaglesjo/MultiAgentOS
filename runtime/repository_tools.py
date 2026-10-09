"""Repository and MCP bindings for the normalized ToolRuntime."""
from __future__ import annotations
from dataclasses import dataclass
from core.contracts.mcp import MCPToolCall
from core.contracts.execution_mission import ExecutionMission, MissionOperation
from core.contracts.agent_execution_runtime import ToolRequest, ToolSideEffect, ToolSpec
from runtime.git import GitRuntime
from runtime.github import GitHubRuntime
from runtime.execution_route import select_execution_route
from runtime.mcp.client import MCPClient
from runtime.tool_calling import ToolRuntime

@dataclass
class GitToolBindings:
    project_root: str
    runtime: ToolRuntime
    git: GitRuntime | None = None

    def __post_init__(self) -> None:
        self.git = self.git or GitRuntime(policy=self.runtime.policy)
        self._register()

    def _register(self) -> None:
        self.runtime.register(ToolSpec("git.status","Show Git working tree status.",ToolSideEffect.READ,input_schema={"type":"object"}),self._status)
        self.runtime.register(ToolSpec("git.diff","Show Git diff.",ToolSideEffect.READ,input_schema={"type":"object"}),self._diff)
        self.runtime.register(ToolSpec("git.log","Show recent Git commits.",ToolSideEffect.READ,input_schema={"type":"object"}),self._log)
        self.runtime.register(ToolSpec("git.add","Stage Git paths.",ToolSideEffect.WRITE,frozenset({"git.write"}),{"type":"object"}),self._add)
        self.runtime.register(ToolSpec("git.commit","Create a Git commit.",ToolSideEffect.WRITE,frozenset({"git.write"}),{"type":"object","required":["message"]}),self._commit)
        self.runtime.register(ToolSpec("git.push","Push Git changes.",ToolSideEffect.NETWORK,frozenset({"git.write","network"}),{"type":"object"}),self._push)

    def _result(self,result: object) -> object:
        return {"returncode":result.returncode,"stdout":result.stdout,"stderr":result.stderr}

    def _status(self,r: ToolRequest): return self._result(self.git.status(self.project_root))
    def _diff(self,r: ToolRequest): return self._result(self.git.diff(self.project_root,staged=r.arguments.get("staged") is True,path=r.arguments.get("path") if isinstance(r.arguments.get("path"),str) else None))
    def _log(self,r: ToolRequest): return self._result(self.git.log(self.project_root,int(r.arguments.get("count",10))))
    def _add(self,r: ToolRequest): return self._result(self.git.add(self.project_root,list(r.arguments.get("paths",[])) or None))
    def _commit(self,r: ToolRequest):
        message=r.arguments.get("message")
        if not isinstance(message,str) or not message.strip(): raise ValueError("message must be a non-empty string")
        return self._result(self.git.commit(self.project_root,message,approved=r.metadata.get("approved") is True))
    def _push(self,r: ToolRequest):
        return self._result(self.git.push(self.project_root,str(r.arguments.get("remote","origin")),r.arguments.get("branch") if isinstance(r.arguments.get("branch"),str) else None,approved=r.metadata.get("approved") is True))

@dataclass
class MCPToolBindings:
    runtime: ToolRuntime
    client: MCPClient

    def register_tools(self, tools: tuple[object,...] | None = None) -> tuple[str,...]:
        available=tools if tools is not None else self.client.list_tools()
        ids=[]
        for tool in available:
            qualified=f"mcp.{tool.server_id}.{tool.name}"
            self.runtime.register(ToolSpec(qualified,tool.description or qualified,tool.side_effect,tool.permissions,tool.input_schema,{"source":"mcp","server_id":tool.server_id,"tool_name":tool.name}),self._handler(tool.server_id,tool.name))
            ids.append(qualified)
        return tuple(ids)

    def _handler(self,server_id:str,tool_name:str):
        def invoke(request:ToolRequest):
            result=self.client.call_tool(MCPToolCall(server_id,tool_name,request.arguments,request.session_id))
            if result.is_error:
                raise RuntimeError(f"MCP tool error: {server_id}:{tool_name}")
            return {"content":result.content,"raw":result.raw}
        return invoke


@dataclass
class GitHubToolBindings:
    """Expose bounded GitHub Actions execution through the normalized tool boundary."""

    runtime: ToolRuntime
    github: GitHubRuntime

    def __post_init__(self) -> None:
        self.runtime.register(
            ToolSpec(
                "execution.route.select",
                "Select the deterministic local-first execution route for a WorkUnit.",
                ToolSideEffect.READ,
                input_schema={
                    "type": "object",
                    "properties": {
                        "local_available": {"type": "boolean"},
                        "local_failed": {"type": "boolean"},
                        "force_remote": {"type": "boolean"},
                        "prefer_local": {"type": "boolean"},
                    },
                },
            ),
            self._select_route,
        )
        self.runtime.register(
            ToolSpec(
                "github.actions.run_mission",
                "Run and verify one bounded GitHub Actions execution mission.",
                ToolSideEffect.NETWORK,
                frozenset({"github.actions"}),
                {
                    "type": "object",
                    "required": ["repository", "operation"],
                    "properties": {
                        "repository": {"type": "string"},
                        "source_sha": {"type": "string"},
                        "operation": {"type": "string", "enum": ["test", "package", "verify"]},
                        "mission_id": {"type": "string"},
                    },
                },
            ),
            self._run_mission,
        )

    def _select_route(self, request: ToolRequest) -> object:
        decision = select_execution_route(
            local_available=request.arguments.get("local_available", True) is True,
            local_failed=request.arguments.get("local_failed", False) is True,
            force_remote=request.arguments.get("force_remote", False) is True,
            allow_github_actions=self.runtime.policy.allow_github_actions,
            prefer_local=request.arguments.get("prefer_local", True) is True,
        )
        return {
            "route": decision.route.value,
            "reason": decision.reason,
            "requires_explicit_github_permission": decision.requires_explicit_github_permission,
        }

    def _run_mission(self, request: ToolRequest) -> object:
        repository = request.arguments.get("repository")
        source_sha = request.arguments.get("source_sha")
        operation = request.arguments.get("operation")
        if not all(isinstance(value, str) and value.strip() for value in (repository, operation)):
            raise ValueError("repository and operation must be non-empty strings")
        repository = repository.strip()
        if repository not in self.runtime.policy.allowed_github_repositories:
            raise PermissionError(
                f"GitHub Actions repository is not allowlisted: {repository}"
            )
        try:
            mission_operation = MissionOperation(operation)
        except ValueError as exc:
            raise ValueError(f"unsupported mission operation: {operation}") from exc

        raw_inputs = request.arguments.get("inputs", {})
        if raw_inputs not in ({}, None):
            raise PermissionError(
                "custom GitHub Actions mission inputs are disabled by runtime policy"
            )

        mission_id = request.arguments.get("mission_id")
        if request.work_unit_id:
            expected_mission_id = f"mission-{request.work_unit_id}"
            if mission_id is not None and mission_id != expected_mission_id:
                raise PermissionError(
                    "mission identity is bound to the current WorkUnit"
                )
            mission_id = expected_mission_id
        elif mission_id is None:
            raise ValueError("mission_id or work_unit_id is required")

        workflow = "execution-mission.yml"
        repository_info = self.github.gateway.get_repository(repository)
        ref = repository_info.default_branch
        requested_workflow = request.arguments.get("workflow")
        requested_ref = request.arguments.get("ref")
        if requested_workflow is not None and requested_workflow != workflow:
            raise PermissionError("GitHub Actions workflow is fixed by runtime policy")
        if requested_ref is not None and requested_ref != ref:
            raise PermissionError(
                "GitHub Actions dispatch ref must be the repository default branch"
            )
        if source_sha is None:
            source_sha = self.github.gateway.get_branch(repository, ref).sha
        if not isinstance(source_sha, str) or not source_sha.strip():
            raise ValueError("source_sha must resolve to a non-empty commit SHA")

        mission = ExecutionMission(
            id=str(mission_id),
            repository=repository,
            source_sha=source_sha,
            workflow=workflow,
            operation=mission_operation,
            ref=ref,
            inputs=dict(raw_inputs),
            expected_artifacts=("execution-mission-evidence",),
        )
        result = self.github.run_actions_mission(mission)
        evidence = result.evidence
        return {
            "mission_id": evidence.mission_id,
            "run_id": evidence.run_id,
            "status": evidence.status,
            "conclusion": evidence.conclusion,
            "source_sha": evidence.source_sha,
            "head_sha": evidence.head_sha,
            "url": evidence.url,
            "artifacts": list(evidence.artifacts),
            "logs_available": evidence.logs_available,
            "disposition": evidence.disposition.value,
        }

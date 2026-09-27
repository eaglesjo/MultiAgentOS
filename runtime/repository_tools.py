"""Repository and MCP bindings for the normalized ToolRuntime."""
from __future__ import annotations
from dataclasses import dataclass
from core.contracts.mcp import MCPToolCall
from core.contracts.vyrelon_runtime import ToolRequest, ToolSideEffect, ToolSpec
from runtime.git import GitRuntime
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

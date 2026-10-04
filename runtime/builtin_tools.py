"""Built-in AGENT_EXECUTION_RUNTIME tool bindings."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from core.contracts.agent_execution_runtime import ToolRequest, ToolSideEffect, ToolSpec
from runtime.local.filesystem import FilesystemRuntime
from runtime.local.patch import PatchRuntime
from runtime.local.shell import PersistentShellRuntime
from runtime.tool_calling import ToolRuntime

@dataclass
class BuiltinToolBindings:
    project_root: str
    runtime: ToolRuntime
    filesystem: FilesystemRuntime | None = None
    patch: PatchRuntime | None = None
    shell: PersistentShellRuntime | None = None

    def __post_init__(self) -> None:
        self.filesystem = self.filesystem or FilesystemRuntime(policy=self.runtime.policy)
        self.patch = self.patch or PatchRuntime(policy=self.runtime.policy)
        self.shell = self.shell or PersistentShellRuntime(self.project_root, policy=self.runtime.policy)
        self._register()

    def _register(self) -> None:
        self.runtime.register(ToolSpec("filesystem.read","Read a text file inside the project root.",ToolSideEffect.READ,input_schema={"type":"object","required":["path"]}),self._read)
        self.runtime.register(ToolSpec("filesystem.write","Write text to a file inside the project root.",ToolSideEffect.WRITE,frozenset({"filesystem.write"}),{"type":"object","required":["path","content"]}),self._write)
        self.runtime.register(ToolSpec("patch.apply","Check and apply a unified Git patch to the project.",ToolSideEffect.WRITE,frozenset({"filesystem.write"}),{"type":"object","required":["patch"]}),self._patch)
        self.runtime.register(ToolSpec("shell.run","Run a command in the project root.",ToolSideEffect.EXECUTE,frozenset({"process"}),{"type":"object","required":["command"]}),self._shell)

    def _path(self, request: ToolRequest) -> str:
        value=request.arguments.get("path")
        if not isinstance(value,str) or not value: raise ValueError("path must be a non-empty string")
        return str(Path(self.project_root)/value)

    def _approved(self, request: ToolRequest) -> bool:
        return request.metadata.get("approved") is True

    def _read(self, request: ToolRequest) -> object:
        return self.filesystem.read_text(self._path(request))

    def _write(self, request: ToolRequest) -> object:
        content=request.arguments.get("content")
        if not isinstance(content,str): raise ValueError("content must be a string")
        return str(self.filesystem.write_text(self._path(request),content,approved=self._approved(request)))

    def _patch(self, request: ToolRequest) -> object:
        patch=request.arguments.get("patch")
        if not isinstance(patch,str) or not patch.strip(): raise ValueError("patch must be a non-empty string")
        result=self.patch.apply(self.project_root,patch,approved=self._approved(request))
        return {"returncode":result.returncode,"stdout":result.stdout,"stderr":result.stderr}

    def _shell(self, request: ToolRequest) -> object:
        command=request.arguments.get("command")
        if not isinstance(command,str) or not command.strip(): raise ValueError("command must be a non-empty string")
        result=self.shell.run(command)
        return {"command":result.command,"cwd":result.cwd,"returncode":result.returncode,"stdout":result.stdout,"stderr":result.stderr}

"""Execution policy primitives for local and repository operations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionPolicy:
    allow_process: bool = True
    allow_filesystem_write: bool = True
    allow_git_write: bool = False
    allow_network: bool = False
    allow_github_write: bool = False
    require_approval_for: frozenset[str] = frozenset({"git.push", "github.pr", "github.merge"})

    def permits(self, capability: str) -> bool:
        mapping = {
            "process": self.allow_process,
            "filesystem.write": self.allow_filesystem_write,
            "git.write": self.allow_git_write,
            "network": self.allow_network,
            "github.write": self.allow_github_write,
        }
        return mapping.get(capability, False)

    def requires_approval(self, action: str) -> bool:
        return action in self.require_approval_for

"""Execution policy primitives for local and repository operations."""

from dataclasses import dataclass

from core.contracts.approval import ApprovalGrant


@dataclass(frozen=True)
class ExecutionPolicy:
    allow_process: bool = True
    allow_filesystem_write: bool = True
    allow_git_write: bool = False
    allow_network: bool = False
    allow_github_write: bool = False
    allow_github_actions: bool = False
    allowed_github_repositories: frozenset[str] = frozenset()
    require_approval_for: frozenset[str] = frozenset(
        {"git.commit", "git.push", "github.pr", "github.merge"}
    )

    def permits(self, capability: str) -> bool:
        mapping = {
            "process": self.allow_process,
            "filesystem.write": self.allow_filesystem_write,
            "git.write": self.allow_git_write,
            "network": self.allow_network,
            "github.write": self.allow_github_write,
            "github.actions": self.allow_github_actions,
        }
        return mapping.get(capability, False)

    def requires_approval(self, action: str, capability: str | None = None) -> bool:
        """Return whether an execution action requires explicit approval."""
        return action in self.require_approval_for or (capability is not None and capability in self.require_approval_for)

    def approval_valid(
        self,
        grant: ApprovalGrant | None,
        *,
        action: str,
        capability: str | None = None,
        work_unit_id: str | None = None,
        session_id: str | None = None,
    ) -> bool:
        if not self.requires_approval(action, capability):
            return True
        # Sensitive actions require a concrete execution scope. Exact equality
        # alone is insufficient when both the grant and request omit the scope.
        if not isinstance(work_unit_id, str) or not work_unit_id.strip():
            return False
        if not isinstance(session_id, str) or not session_id.strip():
            return False
        return grant is not None and grant.is_valid(
            action=action,
            work_unit_id=work_unit_id,
            session_id=session_id,
        )

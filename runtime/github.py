"""Policy-controlled GitHub runtime for VYRELON."""

from __future__ import annotations

from core.contracts.github import GitHubGateway
from runtime.policy import ExecutionPolicy


class GitHubRuntime:
    def __init__(self, gateway: GitHubGateway, policy: ExecutionPolicy | None = None) -> None:
        self.gateway = gateway
        self.policy = policy or ExecutionPolicy()

    def _require_write(self) -> None:
        if not self.policy.permits("github.write"):
            raise PermissionError("GitHub write operations are disabled by policy")

    def create_branch(self, repository: str, branch: str, base: str):
        self._require_write()
        return self.gateway.create_branch(repository, branch, base)

    def create_file(self, repository: str, path: str, content: str, branch: str, message: str):
        self._require_write()
        return self.gateway.create_file(repository, path, content, branch, message)

    def update_file(self, repository: str, path: str, content: str, sha: str, branch: str, message: str):
        self._require_write()
        return self.gateway.update_file(repository, path, content, sha, branch, message)

    def create_issue(self, repository: str, title: str, body: str = ""):
        self._require_write()
        return self.gateway.create_issue(repository, title, body)

    def create_pull_request(
        self, repository: str, title: str, body: str, head: str, base: str,
        draft: bool = False, approved: bool = False,
    ):
        self._require_write()
        self._require_approval("github.pr", approved)
        return self.gateway.create_pull_request(repository, title, body, head, base, draft)

    def review_pull_request(self, repository: str, number: int, action: str, body: str = ""):
        self._require_write()
        return self.gateway.review_pull_request(repository, number, action, body)

    def merge_pull_request(
        self, repository: str, number: int, method: str = "squash",
        approved: bool = False,
    ):
        self._require_write()
        self._require_approval("github.merge", approved)
        return self.gateway.merge_pull_request(repository, number, method)

    def _require_approval(self, action: str, approved: bool) -> None:
        if self.policy.requires_approval(action) and not approved:
            raise PermissionError(f"Explicit approval required for: {action}")

"""Provider-neutral GitHub contracts."""

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class GitHubRepository:
    full_name: str
    default_branch: str
    private: bool


@dataclass(frozen=True)
class GitHubBranch:
    name: str
    sha: str


@dataclass(frozen=True)
class GitHubFile:
    path: str
    content: str
    sha: str


@dataclass(frozen=True)
class GitHubIssue:
    number: int
    title: str
    url: str


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    url: str
    head: str
    base: str


@dataclass(frozen=True)
class ReviewResult:
    success: bool
    action: str


@dataclass(frozen=True)
class MergeResult:
    merged: bool
    sha: str | None
    message: str


@dataclass(frozen=True)
class WorkflowRun:
    id: int
    status: str
    conclusion: str | None = None


class GitHubGateway(Protocol):
    def get_repository(self, full_name: str) -> GitHubRepository: ...
    def get_branch(self, full_name: str, branch: str) -> GitHubBranch: ...
    def create_branch(self, full_name: str, branch: str, base: str) -> GitHubBranch: ...
    def get_file(self, full_name: str, path: str, ref: str) -> GitHubFile: ...
    def create_file(self, full_name: str, path: str, content: str, branch: str, message: str) -> str: ...
    def update_file(self, full_name: str, path: str, content: str, sha: str, branch: str, message: str) -> str: ...
    def create_issue(self, full_name: str, title: str, body: str = "") -> GitHubIssue: ...
    def create_pull_request(self, full_name: str, title: str, body: str, head: str, base: str, draft: bool = False) -> PullRequest: ...
    def review_pull_request(self, full_name: str, number: int, action: str, body: str = "") -> ReviewResult: ...
    def merge_pull_request(self, full_name: str, number: int, method: str = "squash") -> MergeResult: ...
    def list_workflows(self, full_name: str, ref: str) -> Sequence[WorkflowRun]: ...

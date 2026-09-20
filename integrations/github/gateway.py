"""GitHub adapter using the locally authenticated GitHub CLI."""

from __future__ import annotations

import base64
import json
import subprocess
from typing import Any

from core.contracts.github import (
    GitHubBranch,
    GitHubFile,
    GitHubRepository,
    GitHubGateway,
    PullRequest,
    WorkflowRun,
)


class GitHubGatewayClient:
    def __init__(self, gh_binary: str = "gh") -> None:
        self.gh_binary = gh_binary

    def _run(self, *args: str) -> Any:
        result = subprocess.run(
            [self.gh_binary, *args],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"gh command failed ({result.returncode}): "
                f"{' '.join(args)}\n{result.stderr.strip()}"
            )
        output = result.stdout.strip()
        return json.loads(output) if output else None

    def get_repository(self, full_name: str) -> GitHubRepository:
        data = self._run("repo", "view", full_name, "--json", "nameWithOwner,defaultBranchRef,isPrivate")
        return GitHubRepository(
            full_name=data["nameWithOwner"],
            default_branch=data["defaultBranchRef"]["name"],
            private=data["isPrivate"],
        )

    def get_branch(self, full_name: str, branch: str) -> GitHubBranch:
        data = self._run(
            "api", f"repos/{full_name}/branches/{branch}",
            "--jq", "{name: .name, sha: .commit.sha}",
        )
        return GitHubBranch(name=data["name"], sha=data["sha"])

    def create_branch(self, full_name: str, branch: str, base: str) -> GitHubBranch:
        base_ref = self.get_branch(full_name, base)
        self._run(
            "api", f"repos/{full_name}/git/refs", "--method", "POST",
            "-f", f"ref=refs/heads/{branch}", "-f", f"sha={base_ref.sha}",
        )
        return GitHubBranch(name=branch, sha=base_ref.sha)

    def get_file(self, full_name: str, path: str, ref: str) -> GitHubFile:
        data = self._run("api", f"repos/{full_name}/contents/{path}", "-f", f"ref={ref}")
        content = base64.b64decode(data["content"]).decode("utf-8")
        return GitHubFile(path=data["path"], content=content, sha=data["sha"])

    def create_file(self, full_name: str, path: str, content: str, branch: str, message: str) -> str:
        encoded = base64.b64encode(content.encode()).decode()
        data = self._run(
            "api", f"repos/{full_name}/contents/{path}", "--method", "PUT",
            "-f", f"message={message}", "-f", f"content={encoded}", "-f", f"branch={branch}",
        )
        return data["commit"]["sha"]

    def update_file(self, full_name: str, path: str, content: str, sha: str, branch: str, message: str) -> str:
        encoded = base64.b64encode(content.encode()).decode()
        data = self._run(
            "api", f"repos/{full_name}/contents/{path}", "--method", "PUT",
            "-f", f"message={message}", "-f", f"content={encoded}",
            "-f", f"sha={sha}", "-f", f"branch={branch}",
        )
        return data["commit"]["sha"]

    def create_pull_request(self, full_name: str, title: str, body: str, head: str, base: str, draft: bool = False) -> PullRequest:
        args = ["pr", "create", "--repo", full_name, "--title", title, "--body", body, "--head", head, "--base", base]
        if draft:
            args.append("--draft")
        data = self._run(*args, "--json", "number,title,url,headRefName,baseRefName")
        return PullRequest(
            number=data["number"],
            title=data["title"],
            url=data["url"],
            head=data["headRefName"],
            base=data["baseRefName"],
        )

    def list_workflows(self, full_name: str, ref: str) -> list[WorkflowRun]:
        data = self._run(
            "run", "list", "--repo", full_name, "--branch", ref,
            "--json", "databaseId,status,conclusion",
        )
        return [
            WorkflowRun(item["databaseId"], item["status"], item["conclusion"])
            for item in data
        ]

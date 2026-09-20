# VYRELON GitHub Connection

VYRELON owns the GitHub integration path.

```text
VYRELON
  -> GitHubRuntime (policy)
  -> GitHubGatewayClient
  -> authenticated gh CLI
  -> GitHub API
```

MultiAgentOS has no Luna-specific repository, agent, or runtime dependency.

Authentication remains external to the repository. Authenticate the host with `gh auth login`, then verify access with:

```bash
multiagentos github probe eaglesjo/MultiAgentOS
```

Expected output includes the repository, default branch, and current default-branch SHA.

GitHub writes remain disabled unless the VYRELON execution policy enables `github.write`. Pull-request creation and merge additionally require explicit approval.

This makes VYRELON the project-level orchestration path while keeping credentials outside source control.

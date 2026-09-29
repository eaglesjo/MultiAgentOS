# Agent Execution Runtime GitHub Connection

The Agent Execution Runtime owns the **local** GitHub integration path.

```
Agent Execution Runtime
  -> GitHubRuntime (policy)
  -> GitHubGatewayClient
  -> authenticated gh CLI
  -> GitHub API
```

MultiAgentOS has no Luna-specific repository, agent, or runtime dependency.

## Local Agent Execution Runtime authentication

Authentication remains external to the repository. Authenticate the host with:

```bash
gh auth login
gh auth status
```

Then verify access with:

```bash
multiagentos github probe OWNER/REPOSITORY
```

Example:

```bash
multiagentos github probe eaglesjo/MultiAgentOS
```

Expected output includes the repository, default branch, and current default-branch SHA.

GitHub writes remain disabled unless the Agent Execution Runtime execution policy enables `github.write`. Pull-request creation and merge additionally require explicit approval.

## This is separate from ChatGPT's GitHub app

There are two different GitHub access paths:

### Local Agent Execution Runtime

```
your machine
  -> Agent Execution Runtime
  -> gh auth
  -> GitHub
```

This gives the local Agent Execution Runtime runtime access to the repositories allowed by the authenticated GitHub CLI account.

### ChatGPT

```
ChatGPT
  -> GitHub app
  -> GitHub authorization
  -> repositories explicitly selected by the user
```

Connecting GitHub to ChatGPT does **not** grant ChatGPT access to your local filesystem or local Agent Execution Runtime process.

OpenAI's current GitHub connection flow sends the user to GitHub to install/authorize the ChatGPT app and select the repositories it may access.

Official OpenAI guidance:
https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt

## Credentials

Never commit:

- GitHub personal access tokens
- `gh` credential files
- provider API keys
- tunnel credentials
- `.multiagentos/` runtime state

This makes Agent Execution Runtime the project-level orchestration path while keeping credentials outside source control.

For the full user setup, see [Getting Started](GETTING_STARTED.md).

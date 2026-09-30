# Agent Execution Runtime Connection Guide

The Agent Execution Runtime is installed locally and keeps the actual MCP capability on the developer's machine. GitHub and local-machine access are complementary connection paths.

## Connection model

The Agent Execution Runtime exposes one MCP server:

```text
                         +--> GitHub Connector / GitHub
                        /
ChatGPT / Codex -------+
                        \
                         +--> Secure MCP Tunnel (optional)
                                  |
                                  v
                            tunnel-client
                                  |
                                  v
                         Agent Execution Runtime MCP Server
                                  |
                                  v
                             Local Project
```

The GitHub path and the local Agent Execution Runtime path solve different problems:

| Path | Purpose | Requires local Agent Execution Runtime |
| --- | --- | --- |
| ChatGPT -> GitHub | Repository inspection, issues, PRs and durable GitHub state | No |
| Local Agent Execution Runtime -> GitHub | Local Agent Execution Runtime GitHub operations through `gh` | Yes |
| MCP Client -> Agent Execution Runtime | Free/local MCP access | Yes |
| ChatGPT/Codex -> Secure MCP Tunnel -> Agent Execution Runtime | Remote access to the developer's private/local project | Yes |
| Codex -> tunnel-mcp -> tunnel-client | Tunnel runtime operations | Yes, when targeting Agent Execution Runtime |

Secure MCP Tunnel and `tunnel-client` are transport/connection infrastructure. They are not another MCP server.

## 1. Install Agent Execution Runtime

From the MultiAgentOS checkout:

```bash
python -m pip install .
multiagentos --help
```

For an existing project:

```bash
cd your-project
multiagentos init . --component all
multiagentos status .
```

The Agent Execution Runtime remains usable without OpenAI, ChatGPT, a `tunnel_id`, or `tunnel-client`.

## 2. Connect GitHub

### A. ChatGPT GitHub connection

This is the GitHub-native path used when ChatGPT needs repository access.

1. Connect GitHub in ChatGPT Settings -> Apps.
2. In GitHub, install/authorize the ChatGPT GitHub application.
3. Grant access only to the repositories that ChatGPT should use.
4. In ChatGPT, provide the repository URL and the requested development task.

This path gives ChatGPT access to the selected remote repository. It does not give ChatGPT access to the developer's local filesystem.

For repositories using repository-level agent guidance, Agent Execution Runtime can coexist with an `AGENTS.md` / Agent Skills workflow. The repository's own engineering instructions remain authoritative.

### B. Local Agent Execution Runtime GitHub connection

Agent Execution Runtime can also operate against GitHub from the developer's machine:

```text
Local Project
    |
    v
Agent Execution Runtime GitHub Runtime
    |
    v
gh auth
    |
    v
GitHub
```

Configure it with:

```bash
gh auth login
gh auth status
multiagentos github probe OWNER/REPOSITORY
```

GitHub write operations remain subject to Agent Execution Runtime policy and approval.

## 3. Use Agent Execution Runtime locally without OpenAI

The standalone MCP path is:

```text
MCP Client
    |
    | MCP / stdio
    v
Agent Execution Runtime MCP Server
    |
    v
Local Project
```

Start it with:

```bash
multiagentos mcp serve --path /absolute/path/to/project
```

The default surface is read-only.

Opt into writes/process execution explicitly:

```bash
multiagentos mcp serve \
  --path /absolute/path/to/project \
  --allow-write \
  --allow-process
```

No OpenAI account or tunnel is required for this path.

## 4. Connect ChatGPT to the local Agent Execution Runtime project

When ChatGPT needs access to the local/private project, use Secure MCP Tunnel:

```text
ChatGPT / Codex
      |
      | MCP
      v
Secure MCP Tunnel
      |
      v
tunnel-client
      |
      | stdio
      v
Agent Execution Runtime MCP Server
      |
      v
Local Project
```

The managed runtime form is:

```bash
tunnel-client runtimes connect \
  --alias agent-execution-runtime-local \
  --tunnel-id tunnel_... \
  --runtime-api-key env:CONTROL_PLANE_API_KEY \
  --mcp-command "multiagentos mcp serve --path /absolute/path/to/project"
```

Then verify:

```bash
tunnel-client runtimes status agent-execution-runtime-local --json
```

Only after the runtime is healthy should the ChatGPT connector be configured with **Connection: Tunnel**.

See [Secure MCP Tunnel Setup](MCP_TUNNEL.md) for tunnel creation, credential separation, readiness checks, and troubleshooting.

## 5. Codex

The OpenAI `tunnel-client` distribution includes a thin Codex operator surface for tunnel management. It does not replace the Agent Execution Runtime MCP server.

```bash
tunnel-client codex plugin install
tunnel-client codex status
tunnel-client codex diagnose --json
```

For a persistent local runtime, use the native `tunnel-client runtimes ...` commands.

## 6. Recommended developer workflow

For a developer using both GitHub and local Agent Execution Runtime:

```text
                         GitHub
                           ^
                           |
                  ChatGPT GitHub app
                           |
                           |
ChatGPT / Codex ------------+
       |
       | local/private work
       v
Secure MCP Tunnel (optional)
       |
       v
 tunnel-client
       |
       v
 Agent Execution Runtime MCP Server
       |
       v
 Local Project
```

Use GitHub for durable repository state and remote repository collaboration. Use the Agent Execution Runtime for the local project, local execution, and local MCP capabilities.

The two paths should not be collapsed into a single server or credential boundary.

## Credential rules

Keep credentials outside repositories:

- GitHub credentials managed by `gh` or the GitHub connection.
- `CONTROL_PLANE_API_KEY` for tunnel runtime use.
- `OPENAI_ADMIN_KEY` only for tunnel administration.
- Never commit provider keys, GitHub tokens, tunnel credentials, or `.multiagentos/` runtime state.

## References

- [Agent Execution Runtime MCP Architecture](ARCHITECTURE_DECISIONS.md)
- [MCP durable recovery contract](ARCHITECTURE_DECISIONS.md#mcp-durable-recovery-contract)
- [Secure MCP Tunnel Setup](MCP_TUNNEL.md)
- [Agent Execution Runtime GitHub Connection](AGENT_EXECUTION_RUNTIME_GITHUB_CONNECTION.md)

# Getting Started

This guide takes a developer from a clean machine to a usable VYRELON installation and then through the available GitHub and local-project connection paths.

## 1. What you install

MultiAgentOS installs the local VYRELON runtime and CLI.

It is intentionally separate from:

- ChatGPT's GitHub app/connection
- GitHub authentication used by the local CLI
- OpenAI Secure MCP Tunnel
- `tunnel-client`
- Codex's tunnel operator plugin

These are complementary integration paths.

## 2. Cost-free baseline

The core VYRELON runtime is intentionally independent of paid model APIs. A clean installation can use the local MCP server for filesystem READ/WRITE, patch application, and process/test execution without an OpenAI, Anthropic, Gemini, or other paid model API key.

The verified acceptance evidence is maintained in [Cost-Free Development Baseline](COSTFREE_DEVELOPMENT.md). This is an **AI API cost** requirement; it does not assert that every optional AI product or account is free.

Current verification:

- VYRELON MCP: PASS
- filesystem WRITE/READ: PASS
- `patch.apply`: PASS
- `shell.run`: PASS
- local MCP/runtime tests: 10/10 PASS
- Secure MCP Tunnel: READY
- ChatGPT Web write-capable custom MCP: plan-gated on the current Free account

## 3. Install VYRELON

From a MultiAgentOS checkout:

```bash
python -m pip install .
multiagentos --help
```

Initialize an existing project:

```bash
cd your-project
multiagentos init . --component all
multiagentos status .
```

The initializer writes project-local `.multiagentos/` configuration and runtime state. Credentials must remain outside that state.

VYRELON's standalone MCP server does not require OpenAI, ChatGPT, a `tunnel_id`, or `tunnel-client`.

## 4. Choose your connection path

| Goal | Path | VYRELON required |
| --- | --- | --- |
| ChatGPT works on a GitHub repository | ChatGPT -> GitHub app -> authorized repository | No |
| Local VYRELON works with GitHub | VYRELON -> `gh` -> GitHub | Yes |
| Any MCP client uses VYRELON locally | MCP Client -> VYRELON MCP Server | Yes |
| ChatGPT/Codex reaches the local project | ChatGPT/Codex -> Secure MCP Tunnel -> `tunnel-client` -> VYRELON MCP Server | Yes |
| Codex manages tunnel runtime | Codex -> tunnel-mcp -> `tunnel-client` | When using the tunnel path |

The architecture has one actual VYRELON MCP server. Secure MCP Tunnel and `tunnel-client` are transport/connection infrastructure.

## 5. ChatGPT + GitHub

Use this when the work can be performed against the remote repository without local filesystem access.

1. Open ChatGPT Settings -> Apps.
2. Connect GitHub.
3. In GitHub, authorize the ChatGPT GitHub application.
4. Grant access to only the repositories that should be available.
5. In ChatGPT, provide the repository URL and the development task.

This connection gives ChatGPT access to the selected GitHub repository. It does not give ChatGPT access to the developer's local filesystem.

A repository can also carry its own `AGENTS.md` / Agent Skills instructions. Those project instructions remain authoritative.

## 6. Local VYRELON + GitHub

Install GitHub CLI and authenticate it:

```bash
gh auth login
gh auth status
```

Then verify VYRELON can reach a repository:

```bash
multiagentos github probe OWNER/REPOSITORY
```

Example:

```bash
multiagentos github probe eaglesjo/MultiAgentOS
```

This is a separate path from the ChatGPT GitHub connection:

```text
Local VYRELON -> gh -> GitHub
ChatGPT       -> GitHub app -> authorized repositories
```

Do not put GitHub tokens in the repository.

## 7. Standalone VYRELON MCP

From the project you want VYRELON to expose:

```bash
multiagentos mcp serve --path /absolute/path/to/project
```

The default MCP surface is read-only.

To explicitly expose writes and process execution:

```bash
multiagentos mcp serve \
  --path /absolute/path/to/project \
  --allow-write \
  --allow-process
```

- `--allow-write` exposes filesystem write/patch tools.
- `--allow-process` exposes shell execution.
- Without either flag, those side-effecting tools are not advertised.

This path is free/local and can be used by an MCP client without OpenAI.

## 8. ChatGPT/Codex + local VYRELON

Use OpenAI Secure MCP Tunnel when the MCP server must remain on the developer's private/local machine.

The connection is:

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
VYRELON MCP Server
      |
      v
Local Project
```

The managed runtime setup is:

```bash
tunnel-client runtimes connect \
  --alias vyrelon-local \
  --tunnel-id tunnel_... \
  --runtime-api-key env:CONTROL_PLANE_API_KEY \
  --mcp-command "multiagentos mcp serve --path /absolute/path/to/project"
```

Verify the runtime before using the ChatGPT connector:

```bash
tunnel-client runtimes status vyrelon-local --json
```

Then in ChatGPT:

1. Open the connector settings.
2. Choose **Connection: Tunnel**.
3. Select or enter the corresponding tunnel.
4. Confirm the runtime is healthy.
5. Start with a read-only VYRELON MCP operation.

Do not paste a local MCP URL into ChatGPT.

See [Secure MCP Tunnel Setup](MCP_TUNNEL.md) for the complete key/tunnel/runtime procedure.

## 9. Codex tunnel operations

The OpenAI `tunnel-client` distribution provides a thin Codex operator surface:

```bash
tunnel-client codex plugin install
tunnel-client codex status
tunnel-client codex diagnose --json
```

For a persistent runtime, use the native `tunnel-client runtimes ...` commands.

The Codex plugin does not replace VYRELON's MCP server.

## 10. Validate the local installation

Run:

```bash
multiagentos --help
multiagentos status .
python -m unittest discover -s tests -v
python tests/mcp_stdio_smoke.py
```

For GitHub:

```bash
gh auth status
multiagentos github probe OWNER/REPOSITORY
```

For the tunnel path, also verify:

```bash
tunnel-client runtimes status vyrelon-local --json
```

A successful local MCP smoke test does not by itself prove that the external ChatGPT/Codex tunnel is working. End-to-end tunnel validation requires a real OpenAI workspace, tunnel, runtime API key, and running `tunnel-client`.

## 11. Credential rules

Never commit:

- `OPENAI_API_KEY`
- `OPENAI_ADMIN_KEY`
- `CONTROL_PLANE_API_KEY`
- GitHub personal access tokens
- provider API keys
- tunnel runtime secrets
- `.multiagentos/` runtime state

For Secure MCP Tunnel:

- `OPENAI_ADMIN_KEY` is for tunnel administration.
- `CONTROL_PLANE_API_KEY` is for runtime use.
- `CONTROL_PLANE_TUNNEL_ID` identifies the tunnel.

Do not use an admin key as a long-lived runtime credential.

## 12. Next documents

- [VYRELON Connection Guide](VYRELON_CONNECTIONS.md)
- [Secure MCP Tunnel Setup](MCP_TUNNEL.md)
- [VYRELON GitHub Connection](VYRELON_GITHUB_CONNECTION.md)
- [VYRELON MCP Architecture](ARCHITECTURE_DECISIONS.md)

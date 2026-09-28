# Getting Started

This guide takes a new user from a clean machine to a validated MultiAgentOS/VYRELON development environment, including the VYRELON MCP server path for local/private access.

## 1. What you are installing

MultiAgentOS provides the local VYRELON orchestration runtime. It is intentionally separate from:

- ChatGPT's GitHub app/connector
- GitHub authentication used by the local CLI
- OpenAI Secure MCP Tunnel
- Codex's local tunnel MCP plugin

These are different integration paths and must not be confused.

## 2. Install MultiAgentOS

From a checkout:

```bash
python -m pip install .
multiagentos --help
```

For a project:

```bash
cd your-project
multiagentos init . --component all
multiagentos status .
```

The initializer creates project-local `.multiagentos/` configuration and runtime state. Runtime state is ignored by Git and must not contain credentials.

## 3. Configure GitHub for local VYRELON

The local GitHub runtime uses the authenticated `gh` CLI.

Install GitHub CLI using the official GitHub CLI installation instructions, then:

```bash
gh auth login
gh auth status
multiagentos github probe OWNER/REPOSITORY
```

Example:

```bash
multiagentos github probe eaglesjo/MultiAgentOS
```

This path is **local VYRELON -> gh -> GitHub**. It is independent from the ChatGPT GitHub app.

See [VYRELON GitHub Connection](VYRELON_GITHUB_CONNECTION.md).

## 4. Connect GitHub to ChatGPT

If you want ChatGPT itself to inspect an allowed GitHub repository:

1. Open ChatGPT Settings.
2. Open Apps (the UI may use an older Connectors/Plugins label).
3. Select GitHub.
4. Continue to GitHub.
5. Install/authorize the ChatGPT GitHub app.
6. Select the repositories that ChatGPT is allowed to access.
7. Return to ChatGPT and verify the GitHub app is connected.

Do **not** put a personal GitHub token into the MultiAgentOS repository or README.

This path is **ChatGPT -> GitHub app -> allowed repositories**. It does not provide ChatGPT with access to your local filesystem.

Official OpenAI guidance:
https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt

## 5. Start the VYRELON MCP server locally

From the project you want to expose:

```bash
multiagentos mcp serve --path /absolute/path/to/project
```

The default MCP surface is read-only. To expose additional capabilities, opt in explicitly:

```bash
multiagentos mcp serve --path /absolute/path/to/project --allow-write --allow-process
```

- `--allow-write` exposes filesystem write and patch tools.
- `--allow-process` exposes shell execution.
- Without either flag, write/patch/process tools are not advertised.

## 6. Local access from ChatGPT: Secure MCP Tunnel

For ChatGPT to reach a private/local MCP server, use OpenAI Secure MCP Tunnel. Do not expose a localhost MCP endpoint directly to the public internet.

The current tunnel flow is:

```
ChatGPT
  |
  | Connection: Tunnel + tunnel_id
  v
OpenAI Secure MCP Tunnel
  |
  | outbound polling
  v
tunnel-client
  |
  | --mcp-command
  v
multiagentos mcp serve --path /absolute/path/to/project
  |
  v
VYRELON local tool policy
```

No inbound port is required for the tunnel itself; `tunnel-client` makes outbound HTTPS connections to OpenAI and separately reaches the configured MCP server.

See [MCP Tunnel Setup](MCP_TUNNEL.md).

## 7. Connect the ChatGPT connector

In ChatGPT connector settings:

1. Choose **Connection: Tunnel**.
2. Select or enter the `tunnel_id`.
3. Do **not** paste the private/local MCP URL into ChatGPT.
4. Confirm the tunnel runtime is healthy.
5. Start with a safe read-only VYRELON tool call.

A local MCP server passing its own tests does not prove that the remote ChatGPT connector is configured; end-to-end validation requires a real tunnel runtime and workspace permissions.

## 8. Codex integration

The current MultiAgentOS release contains an MCP **client/proxy** runtime and policy layer. It can connect to MCP servers over stdio and Streamable HTTP.

It does **not yet expose the VYRELON runtime itself as a public-facing MCP server endpoint**.

Therefore, the following is currently supported:

```
VYRELON -> MCP server
```

and, with Secure MCP Tunnel:

```
ChatGPT -> Tunnel -> tunnel-client -> an MCP server
```

The following is **not yet a completed MultiAgentOS feature**:

```
ChatGPT -> Tunnel -> tunnel-client -> VYRELON MCP server endpoint
```

Do not claim this last path is installed or working until a VYRELON MCP server adapter and end-to-end test have been added.

## 9. Codex integration

The OpenAI `tunnel-client` project provides a Codex-local Tunnel MCP plugin.

When `tunnel-client` is installed:

```bash
tunnel-client codex plugin install
tunnel-client codex status
tunnel-client codex diagnose --json
```

For a persistent runtime, use the native `tunnel-client runtimes ...` command family. The plugin is a thin Codex operator surface; it does not replace the tunnel client.

See [MCP Tunnel Setup](MCP_TUNNEL.md) for the security/key separation and runtime verification flow.

Official tunnel-client documentation:
https://github.com/openai/tunnel-client

## 10. Verify the complete local installation

Run:

```bash
multiagentos --help
multiagentos status .
python -m unittest discover -s tests -v
```

If GitHub access is required:

```bash
gh auth status
multiagentos github probe OWNER/REPOSITORY
```

For tunnel-based access, verify the tunnel runtime with `tunnel-client` before testing connector discovery or tool calls.

## 11. Credential rules

Never commit:

- `OPENAI_API_KEY`
- `OPENAI_ADMIN_KEY`
- `CONTROL_PLANE_API_KEY`
- GitHub personal access tokens
- provider API keys
- tunnel runtime secrets
- `.multiagentos/` runtime state

For Secure MCP Tunnel, keep the key split:

- `OPENAI_ADMIN_KEY`: tunnel CRUD/admin operations only.
- `CONTROL_PLANE_API_KEY`: long-lived runtime polling/use.
- `CONTROL_PLANE_TUNNEL_ID`: identifies the tunnel.

Do not put an admin key into a long-lived daemon profile.

## 12. Integration map

| Need | Path |
|---|---|
| Local orchestration | MultiAgentOS -> VYRELON |
| Local GitHub operations | VYRELON -> gh -> GitHub |
| ChatGPT repository access | ChatGPT -> GitHub app |
| ChatGPT local/private VYRELON | ChatGPT -> Secure MCP Tunnel -> tunnel-client -> `multiagentos mcp serve` |
| Codex tunnel operations | Codex -> tunnel-mcp plugin -> tunnel-client |


The VYRELON MCP server is implemented locally; the remaining environment-specific step is configuring and validating the real Secure MCP Tunnel and ChatGPT workspace connector.

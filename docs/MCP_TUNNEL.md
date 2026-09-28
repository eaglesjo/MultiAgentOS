# Secure MCP Tunnel Setup

This document describes the supported OpenAI Secure MCP Tunnel path and how it connects to the VYRELON stdio MCP server.

## Architecture

```
ChatGPT
  |
  | Connection: Tunnel
  | tunnel_id
  v
OpenAI Secure MCP Tunnel
  |
  | outbound HTTPS polling
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

The tunnel client does not require an inbound port for the tunnel itself. It needs outbound HTTPS access to OpenAI and access to the configured MCP server.

## Prerequisites

- An OpenAI workspace with Secure MCP Tunnel access.
- A `tunnel_id`.
- A runtime API key with the permissions required to use the tunnel.
- `tunnel-client` installed on the machine that can reach the local VYRELON project.
- MultiAgentOS installed so `multiagentos mcp serve` is available on `PATH`.

The current OpenAI tunnel documentation distinguishes runtime credentials from tunnel administration credentials.

## 1. Start VYRELON as an MCP server

From the project you want to expose:

```bash
multiagentos mcp serve --path /absolute/path/to/project
```

The server uses stdio JSON-RPC and does not listen on a TCP port. By default it exposes read-only tools.

Additional capabilities require explicit startup flags:

```bash
multiagentos mcp serve --path /absolute/path/to/project --allow-write --allow-process
```

Use these deliberately: `--allow-write` exposes filesystem write/patch tools and `--allow-process` exposes shell execution.

## 2. Key separation

Use separate credentials for separate jobs:

```
CONTROL_PLANE_TUNNEL_ID
    -> identifies the tunnel

CONTROL_PLANE_API_KEY
    -> long-lived runtime key used by tunnel-client

OPENAI_ADMIN_KEY
    -> tunnel CRUD/administration only
```

Do not put `OPENAI_ADMIN_KEY` in a long-lived daemon configuration.

## 3. Create or select the tunnel

Tunnel administration is performed through the OpenAI Tunnels management surface or the `tunnel-client admin tunnels ...` commands when the operator has the required permissions.

The exact workspace and permission model is controlled by OpenAI. Keep the resulting `tunnel_id` available for the connector configuration.

## 4. Configure the local runtime

For a local stdio MCP server, the tunnel-client documentation provides an initialization pattern similar to:

```bash
tunnel-client init \
  --sample sample_mcp_stdio_local \
  --profile vyrelon-local \
  --tunnel-id tunnel_... \
  --mcp-command "multiagentos mcp serve --path /absolute/path/to/project"
```

Validate before running:

```bash
tunnel-client doctor --profile local-stdio --explain
tunnel-client run --profile local-stdio
```

Keep the tunnel process running while ChatGPT uses the connector.

## 5. ChatGPT connector configuration

In ChatGPT connector settings:

1. Choose **Connection: Tunnel**.
2. Select the available tunnel, or enter the `tunnel_id`.
3. Do **not** paste the private/local MCP server URL into ChatGPT.
4. Confirm the tunnel runtime is healthy before testing tool discovery.

The current connector surface uses the tunnel ID rather than asking the user to expose the local MCP URL.

## 6. Readiness and troubleshooting

Before reporting that a tunnel connection works:

```bash
tunnel-client doctor --profile local-stdio --explain
```

or use the appropriate runtime status command:

```bash
tunnel-client runtimes list
tunnel-client runtimes status <alias>
```

Check:

- tunnel ID is correct
- runtime API key has Tunnels Read + Use
- tunnel is associated with the correct workspace
- tunnel-client can reach the local MCP server
- outbound HTTPS to OpenAI is allowed
- the tunnel process remains running

If the tunnel is visible in OpenAI Platform but not in ChatGPT, verify the workspace association and connector permissions.

## 7. Codex plugin

If Codex is installed locally and the tunnel-client binary is available:

```bash
tunnel-client codex plugin install
tunnel-client codex status
tunnel-client codex diagnose --json
```

For a persistent runtime, use:

```bash
tunnel-client runtimes list
tunnel-client runtimes status <alias>
```

If the plugin was installed while Codex was already running, restart the Codex session so the plugin inventory is reloaded.

The plugin is an operator surface over native `tunnel-client runtimes ...` commands; tunnel protocol logic remains in the tunnel-client binary.

## 8. MultiAgentOS boundary

MultiAgentOS currently provides:

- VYRELON stdio MCP server via `multiagentos mcp serve`
- read-only-by-default MCP tool exposure
- explicit write/process opt-in flags
- MCP contracts
- MCP stdio and Streamable HTTP client support
- MCP session management
- MCP tool authorization and side-effect policy
- MCP tool proxying
- local MCP configuration examples

MultiAgentOS does **not** provide:

- a built-in `tunnel-client` binary
- automatic OpenAI tunnel provisioning
- automatic ChatGPT connector configuration

The supported implementation path is:

```
ChatGPT -> Secure MCP Tunnel -> tunnel-client -> VYRELON MCP server
```

The final connector/runtime step remains environment-specific and must be validated with the user's actual OpenAI workspace, tunnel ID, permissions, and running `tunnel-client` process.

## Official references

- OpenAI tunnel-client: https://github.com/openai/tunnel-client
- Connector behavior: https://github.com/openai/tunnel-client/blob/master/docs/connectors.md
- Permissions: https://github.com/openai/tunnel-client/blob/master/docs/permissions.md
- End-user guide: https://github.com/openai/tunnel-client/blob/master/docs/end-user-guide.md

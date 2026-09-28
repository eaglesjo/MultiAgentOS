# Secure MCP Tunnel Setup

This document describes the supported OpenAI Secure MCP Tunnel path and how it relates to MultiAgentOS.

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
  +--> local/private MCP server
```

The tunnel client does not require an inbound port for the tunnel itself. It needs outbound HTTPS access to OpenAI and access to the configured MCP server.

## Prerequisites

- An OpenAI workspace with Secure MCP Tunnel access.
- A `tunnel_id`.
- A runtime API key with the permissions required to use the tunnel.
- `tunnel-client` installed on the machine that can reach the local/private MCP server.

The current OpenAI tunnel documentation distinguishes runtime credentials from tunnel administration credentials.

## Key separation

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

## Create or select the tunnel

Tunnel administration is performed through the OpenAI Tunnels management surface or the `tunnel-client admin tunnels ...` commands when the operator has the required permissions.

The exact workspace and permission model is controlled by OpenAI. Keep the resulting `tunnel_id` available for the connector configuration.

## Configure the local runtime

For a local stdio MCP server, the tunnel-client documentation provides an initialization pattern similar to:

```bash
tunnel-client init \
  --sample sample_mcp_stdio_local \
  --profile local-stdio \
  --tunnel-id tunnel_... \
  --mcp-command "python /path/to/server.py"
```

Validate before running:

```bash
tunnel-client doctor --profile local-stdio --explain
tunnel-client run --profile local-stdio
```

Keep the tunnel process running while ChatGPT uses the connector.

## ChatGPT connector configuration

In ChatGPT connector settings:

1. Choose **Connection: Tunnel**.
2. Select the available tunnel, or enter the `tunnel_id`.
3. Do **not** paste the private/local MCP server URL into ChatGPT.
4. Confirm the tunnel runtime is healthy before testing tool discovery.

The current connector surface uses the tunnel ID rather than asking the user to expose the local MCP URL.

## Readiness and troubleshooting

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

## Codex plugin

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

## MultiAgentOS boundary

MultiAgentOS currently provides:

- MCP contracts
- MCP stdio and Streamable HTTP client support
- MCP session management
- MCP tool authorization and side-effect policy
- MCP tool proxying
- local MCP configuration examples

MultiAgentOS currently does **not** provide:

- a VYRELON MCP server endpoint that accepts ChatGPT connector traffic
- a built-in `tunnel-client` binary
- automatic OpenAI tunnel provisioning
- automatic ChatGPT connector configuration

Therefore, do not document the following as a completed setup:

```
ChatGPT -> Tunnel -> VYRELON
```

The required next implementation is a VYRELON MCP server adapter exposing a deliberately scoped tool surface, followed by an end-to-end tunnel/connector test.

## Official references

- OpenAI tunnel-client: https://github.com/openai/tunnel-client
- Connector behavior: https://github.com/openai/tunnel-client/blob/master/docs/connectors.md
- Permissions: https://github.com/openai/tunnel-client/blob/master/docs/permissions.md
- End-user guide: https://github.com/openai/tunnel-client/blob/master/docs/end-user-guide.md

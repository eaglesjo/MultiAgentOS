# Secure MCP Tunnel Setup

This document describes the supported OpenAI Secure MCP Tunnel path and how it connects to the Agent Execution Runtime stdio MCP server.

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
Agent Execution Runtime local tool policy
```

The tunnel client does not require an inbound port for the tunnel itself. It needs outbound HTTPS access to OpenAI and access to the configured MCP server.

## Prerequisites

- An OpenAI workspace with Secure MCP Tunnel access.
- A `tunnel_id`.
- A runtime API key with the permissions required to use the tunnel.
- `tunnel-client` installed on the machine that can reach the local Agent Execution Runtime project.
- MultiAgentOS installed so `multiagentos mcp serve` is available on `PATH`.

The current OpenAI tunnel documentation distinguishes runtime credentials from tunnel administration credentials.

## 1. Start Agent Execution Runtime as an MCP server

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

### Streamable HTTP transport

MultiAgentOS also provides an official MCP Python SDK Streamable HTTP server:

```bash
multiagentos mcp serve-http --path /absolute/path/to/project
```

The MCP endpoint is `http://127.0.0.1:8000/mcp` by default. This path uses the official SDK low-level server and keeps the same Agent Execution Runtime durable bridge and execution policy as stdio. Streamable HTTP does **not** remove filesystem write support: use `--allow-write` to expose `filesystem.write` explicitly.

```bash
multiagentos mcp serve-http \
  --path /absolute/path/to/project \
  --allow-write
```

The custom `runtime/recover` request remains a low-level MCP request extension rather than a normal tool, so durable recovery stays separate from ordinary `tools/call` execution.

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

For a local stdio MCP server, the current managed-runtime path is:

```bash
tunnel-client runtimes connect \
  --alias agent-execution-runtime-local \
  --tunnel-id tunnel_... \
  --runtime-api-key env:CONTROL_PLANE_API_KEY \
  --mcp-command "multiagentos mcp serve --path /absolute/path/to/project"
```

Validate the managed runtime:

```bash
tunnel-client runtimes status agent-execution-runtime-local --json
```

For older/profile-based tunnel-client workflows, the equivalent foreground setup is:

```bash
tunnel-client init \
  --sample sample_mcp_stdio_local \
  --profile agent-execution-runtime-local \
  --tunnel-id tunnel_... \
  --mcp-command "multiagentos mcp serve --path /absolute/path/to/project"

tunnel-client doctor --profile agent-execution-runtime-local --explain
tunnel-client run --profile agent-execution-runtime-local
```

Keep the tunnel runtime/process running while ChatGPT uses the connector.

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

- Agent Execution Runtime stdio MCP server via `multiagentos mcp serve`
- Agent Execution Runtime Streamable HTTP MCP server via `multiagentos mcp serve-http`
- read-only-by-default MCP tool exposure
- explicit write/process opt-in flags on both stdio and Streamable HTTP transports
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
ChatGPT -> Secure MCP Tunnel -> tunnel-client -> Agent Execution Runtime MCP server
```

The final connector/runtime step remains environment-specific and must be validated with the user's actual OpenAI workspace, tunnel ID, permissions, and running `tunnel-client` process.



### Streamable HTTP tunnel binding

For the current OpenAI tunnel-client, a Streamable HTTP MCP server is configured with `MCP_SERVER_URL`. **The tunnel target must be the exact MCP endpoint for the project being exposed. Do not rely on a default port.** For example, when PetTarotReading is the managed project on port `8003`, use `http://127.0.0.1:8003/mcp`. Port `8000` is only an example in generic documentation and must not be assumed to be a gateway. MultiAgentOS can therefore remain loopback-only when tunnel-client runs on the same host:

```bash
multiagentos mcp serve-http --path /absolute/path/to/project --host 127.0.0.1 --port 8000
export MCP_SERVER_URL=http://127.0.0.1:8003/mcp
```

The managed-runtime form is:

```bash
tunnel-client runtimes connect \
  --alias agent-execution-runtime-http \
  --tunnel-id tunnel_... \
  --runtime-api-key env:CONTROL_PLANE_API_KEY \
  --mcp-server-url "$MCP_SERVER_URL"

tunnel-client runtimes status agent-execution-runtime-http --json
```

Treat the runtime as connected only when status reports the managed process running and health available. This is the boundary between local MCP compatibility tests and real Secure MCP Tunnel validation.

Do not publish port 8000 solely for ChatGPT connectivity. The tunnel-client establishes the outbound tunnel; the local MCP server can remain private.

### Acceptance gate for the real tunnel-client

The repository does not store tunnel credentials and CI does not attempt to create or connect an OpenAI tunnel. The final environment-specific gate is the JSON status emitted by the locally installed `tunnel-client`:

```bash
tunnel-client runtimes status agent-execution-runtime-http --json \
  | python tests/tunnel_client_runtime_status.py
```

The gate requires the managed runtime to report all core lifecycle facts plus healthy control-plane polling:

```text
process_running = true
healthy         = true
ready           = true
control_plane_poll_health = healthy/ok
```

This intentionally does not inspect or print the tunnel ID, API key, OAuth tokens, MCP payloads, or endpoint credentials. Control-plane polling is checked only as a health state, never as credential material.

For Streamable HTTP, the binding remains:

```text
MCP_SERVER_URL=http://127.0.0.1:8000/mcp
```

The current tunnel-client documentation identifies Streamable HTTP as the `MCP_SERVER_URL` binding and recommends `runtimes connect` followed by `runtimes status` before declaring the runtime usable.

The tunnel-client 2026-07-28 negotiation issue was also resolved upstream in v0.0.13: the client now uses `server/discover` for the modern protocol before falling back to legacy `initialize`. This is important because MultiAgentOS's modern Streamable HTTP compatibility contract requires 2026-07-28.

For the Streamable HTTP tunnel acceptance gate, run:

```bash
bash tests/tunnel_client_mcp_acceptance.sh
```

In addition to process/health/readiness, this gate requires the tunnel-client `/health/mcp` evidence to report `status=ok`, `state=discovered`, an unbounded discovery result, a complete `tools/list` observation, and the expected `filesystem.read` tool. This is discovery evidence retained by tunnel-client; OpenAI documents that health reads do not perform a fresh MCP probe, so it is not equivalent to a live ChatGPT tool invocation.

## Official references

- OpenAI Secure MCP Tunnel: https://developers.openai.com/api/docs/guides/secure-mcp-tunnels
- tunnel-client repository: https://github.com/openai/tunnel-client
- Latest tunnel-client release: https://github.com/openai/tunnel-client/releases/latest
- tunnel-client end-user guide: https://github.com/openai/tunnel-client/blob/master/docs/end-user-guide.md


### Host compatibility checkpoint

The Streamable HTTP endpoint is now exercised with the official MCP Python SDK client and the official MCP Inspector CLI. Inspector supports ad-hoc Streamable HTTP targets with `--transport http` and the same client configuration model used by its Web/TUI clients. The repository smoke test exercises both `tools/list` and a real `filesystem.read` call against the HTTP endpoint.

A host that supports MCP Streamable HTTP should therefore connect to:

```text
http://127.0.0.1:8000/mcp
```

For a deployed endpoint, configure the host with the HTTPS `/mcp` URL and the required authentication headers. The SDK's default HTTP server security is localhost-only; a non-local deployment must explicitly configure the transport host allowlist. This is an intentional deployment boundary, not a reason to weaken the local default.

Filesystem write remains an explicit capability:

```bash
multiagentos mcp serve-http --path /absolute/path/to/project --allow-write
```

The Host compatibility boundary does not authorize writes by itself; `ExecutionPolicy` remains the authority for `filesystem.write` and `process`.


### Tool invocation acceptance: tunnel-client forwarding path

The repository now has a separate forwarding-level acceptance script:

```bash
bash tests/tunnel_client_tool_invocation.sh
```

This gate starts the real MultiAgentOS Streamable HTTP server, starts the official `tunnel-client dev proxy` local integration mode, then sends MCP JSON-RPC through the tunnel-client ingress and verifies:

- `tools/list`
- an actual `filesystem.read` call
- an actual `filesystem.write` call when `MULTIAGENTOS_ALLOW_WRITE=1`
- a write/read round trip proving the write reached the MultiAgentOS tool runtime

The write path is deliberately enabled for this acceptance test only. Normal MultiAgentOS MCP exposure remains read-only unless `--allow-write` is supplied.

This is stronger than `/health/mcp` discovery evidence because it exercises real `tools/call` traffic through tunnel-client. It uses tunnel-client's local integration control plane, so it does **not** prove that a particular OpenAI workspace or ChatGPT connector can invoke the hosted tunnel.

### Hosted Secure MCP Tunnel tool-call gate

The final hosted boundary is still the actual OpenAI connector path:

```text
ChatGPT / OpenAI product
  -> OpenAI hosted /v1/mcp/{tunnel_id}
  -> tunnel-client
  -> MultiAgentOS /mcp
  -> filesystem.read / filesystem.write
```

OpenAI's current tunnel architecture documents that connector JSON-RPC is POSTed to the hosted tunnel endpoint, queued by the tunnel service, forwarded by tunnel-client, and returned through the same tunnel. The current ChatGPT UI uses **Connection: Tunnel** with the `tunnel_id`; the private `MCP_SERVER_URL` stays on the tunnel-client side.

For the hosted acceptance, use the actual ChatGPT connector and invoke both:

```text
filesystem.read
filesystem.write
filesystem.read   # verify the write
```

Record the corresponding request/response observation on the MultiAgentOS side. The repository intentionally does not automate or store ChatGPT connector credentials, so a hosted tool-call pass cannot be claimed from CI alone.

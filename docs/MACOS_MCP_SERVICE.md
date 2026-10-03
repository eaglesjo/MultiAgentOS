# macOS MCP Service

MultiAgentOS can run its Streamable HTTP MCP server as a per-user macOS `launchd` service.

This is the recommended local runtime shape when the MCP server is used continuously by a local MCP client. Secure MCP Tunnel is optional and is not required for the local cost-free baseline.

## Architecture

```text
macOS user login
      |
      v
launchd
      |
      +--> Project A MCP :8000
      |
      +--> Project B MCP :8001
      |
      +--> Project C MCP :8002

Each service owns exactly one project root.
```

The MultiAgentOS MCP server remains a local process. OpenAI hosts the remote tunnel; `tunnel-client` is the local connector.

## Install

From the MultiAgentOS repository:

```bash
bash scripts/macos/install_mcp_launchd.sh
```

The installer creates a project virtual environment when needed, installs the `mcp-http` extra, registers a per-user launchd service, and starts it immediately.

For the local read/write workflow:

```bash
multiagentos mcp install --path /absolute/path/to/project --allow-write
```

Process execution remains disabled unless explicitly requested:

```bash
multiagentos mcp install --path /absolute/path/to/project --allow-write --allow-process
```

The legacy repository installer remains available for source checkouts:

```bash
bash scripts/macos/install_mcp_launchd.sh --allow-write
```

## Lifecycle

The service uses `RunAtLoad` and `KeepAlive`. Each installed project gets a deterministic service ID derived from its canonical project path. Its launchd label, plist, logs, and endpoint configuration are therefore project-scoped. Reinstalling or uninstalling one project does not remove another project's service.

Use `multiagentos mcp list` to enumerate all project-scoped MCP services. Use `multiagentos mcp status --path /absolute/path/to/project` and `multiagentos mcp uninstall --path /absolute/path/to/project` to target one project only.

Durable MultiAgentOS state remains under `.multiagentos/`.

The service does not embed OpenAI tunnel credentials or API keys in the launchd plist.

## Verify

```bash
multiagentos mcp list
multiagentos mcp status --path /absolute/path/to/project
```

The endpoint is project-specific, for example `http://127.0.0.1:8000/mcp` for one project and `http://127.0.0.1:8001/mcp` for another.

A bare GET may return HTTP 400 with `Missing session ID`. That is expected for a stateful Streamable HTTP MCP endpoint and does not by itself indicate that the server is down.

## Logs

```text
.multiagentos/logs/mcp-launchd.log
.multiagentos/logs/mcp-launchd.error.log
```

## Stop / remove

```bash
multiagentos mcp uninstall --path /absolute/path/to/project
```

Removing the launchd service does not remove `.multiagentos` durable state.

## Design boundary

This service solves the local MCP server lifecycle.

It intentionally does not create an OpenAI tunnel, create or rotate API keys, store secrets in the repository, or make ChatGPT connector configuration changes.

The target local flow is:

```text
launchd -> MultiAgentOS MCP -> local MCP client
```

Secure MCP Tunnel remains an optional remote-connection layer documented separately.
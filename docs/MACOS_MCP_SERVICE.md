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
      +--> explicitly installed project MCP services
             |-- Project A -> :8002
             |-- Project B -> :8003
             `-- ...
```

Only projects for which `multiagentos mcp install` has been explicitly run get a managed service. Service labels and plist paths are project-scoped and deterministic; installing one project never removes another project service.

The MultiAgentOS MCP server remains a local process. OpenAI hosts the remote tunnel; `tunnel-client` is the local connector.

## Install

From the MultiAgentOS repository:

```bash
bash scripts/macos/install_mcp_launchd.sh
```

The installer creates a project virtual environment when needed, installs the `mcp-http` extra, then delegates service registration to the same project-scoped lifecycle used by `multiagentos mcp install`.

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

The service uses `RunAtLoad` and `KeepAlive`. It starts when the user session loads the service and is restarted if the MCP process exits.

Durable MultiAgentOS state remains under `.multiagentos/`.

The service does not embed OpenAI tunnel credentials or API keys in the launchd plist.

## Verify

```bash
multiagentos mcp status --path /absolute/path/to/project
launchctl print gui/$(id -u)/com.eaglesjo.multiagentos.mcp.<project-id>
```

The MCP endpoint is the host/port selected at install time (for example, `http://127.0.0.1:8002/mcp`).

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

## Lifecycle guarantees

On macOS, installation is transactional for the selected project service:

1. The existing project service is unloaded and launchd is polled until it is gone.
2. The new plist is written atomically.
3. The service is bootstrapped and kickstarted.
4. The TCP endpoint is verified before installation reports success.
5. If bootstrap, start, or endpoint readiness fails, the new service is removed and the previous project plist is restored when available.

Uninstall also waits for launchd to unload the project service before removing its plist.

These operations are project-scoped. They do not boot out or delete another project's service.

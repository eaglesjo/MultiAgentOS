# Windows MCP Service

MultiAgentOS can run its Streamable HTTP MCP server as a per-user Windows Task Scheduler task.

This provides the same local-first, cost-free MCP baseline as macOS without requiring Secure MCP Tunnel or a paid AI API key.

## Architecture

```text
Windows user logon
      |
      v
Task Scheduler
      |
      v
MultiAgentOS MCP :8000
      |
      v
Local MCP client
```

## Install

From the MultiAgentOS repository:

```powershell
py -m pip install ".[mcp-http]"
multiagentos mcp install --path C:\Users\<you>\Documents\MultiAgentOS --allow-write
```

The installer creates a per-user Task Scheduler task named:

```text
MultiAgentOS Local MCP
```

It starts the server immediately and configures the task to start at the user's next logon.

Process execution remains disabled unless explicitly requested:

```powershell
multiagentos mcp install --path C:\Users\<you>\Documents\MultiAgentOS --allow-write --allow-process
```

## Verify

Check the managed task:

```powershell
multiagentos mcp status
```

The MCP endpoint is:

```text
http://127.0.0.1:8000/mcp
```

A bare GET may return HTTP 400 with `Missing session ID`. That is expected for a stateful Streamable HTTP MCP endpoint and does not by itself indicate that the server is down.

You can also query Task Scheduler directly:

```powershell
schtasks.exe /Query /TN "MultiAgentOS Local MCP" /FO LIST /V
```

## Stop / remove

```powershell
multiagentos mcp uninstall
```

This removes the managed Task Scheduler task and does not remove `.multiagentos/` project state.

## Manual server

For a one-off session without Task Scheduler:

```powershell
multiagentos mcp serve-http --path . --allow-write
```

## Security boundary

The managed server is restricted to `127.0.0.1`. The service does not create an OpenAI tunnel, create or rotate API keys, or store credentials in the repository.

Secure MCP Tunnel remains an optional remote-connection layer for clients that cannot reach the local MCP server directly.

## macOS and Windows parity

| Capability | macOS | Windows |
| --- | --- | --- |
| Local Streamable HTTP MCP | Yes | Yes |
| Managed install | launchd | Task Scheduler |
| Start immediately | Yes | Yes |
| Start at user logon | Yes | Yes |
| Restart after process exit | launchd KeepAlive | Task Scheduler task lifecycle |
| Status | `multiagentos mcp status` | `multiagentos mcp status` |
| Uninstall | `multiagentos mcp uninstall` | `multiagentos mcp uninstall` |

The managed-service implementation is intentionally OS-native: macOS uses launchd and Windows uses Task Scheduler.

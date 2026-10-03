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

The installer creates a per-user, project-scoped Task Scheduler task named:

```text
MultiAgentOS Local MCP (<project-id>)
```

The project ID is derived deterministically from the canonical project path:

```text
SHA-256(canonical_project_root)[:12]
```

This means separate projects have separate Windows service identities. Installing or uninstalling one project does not target another project's task.

On Windows, Task Scheduler registration may require an Administrator PowerShell depending on the local task-creation policy. The task itself runs as the signed-in user.

It starts the server immediately and configures the task to start at the user's next logon.

The Windows task invokes the windowless `pythonw.exe` interpreter when it is available, with `-m multiagentos.cli mcp serve-http`, so the login-started MCP server does not open a visible console window. It sets the project directory as the Task Scheduler working directory. The installer waits for the local MCP endpoint to become reachable before reporting success.

Process execution remains disabled unless explicitly requested:

```powershell
multiagentos mcp install --path C:\Users\<you>\Documents\MultiAgentOS --allow-write --allow-process
```

## Verify

Check the managed task for a specific project:

```powershell
multiagentos mcp status --path C:\Users\<you>\Documents\MultiAgentOS
```

The MCP endpoint is:

```text
http://127.0.0.1:8000/mcp
```

A bare GET may return HTTP 400 with `Missing session ID`. That is expected for a stateful Streamable HTTP MCP endpoint and does not by itself indicate that the server is down.

You can also query Task Scheduler directly:

```powershell
schtasks.exe /Query /TN "MultiAgentOS Local MCP (<project-id>)" /FO LIST /V
```

## Stop / remove

```powershell
multiagentos mcp uninstall --path C:\Users\<you>\Documents\MultiAgentOS
```

MultiAgentOS first requests the project task to stop with `schtasks /end`, waits until Task Scheduler no longer reports it as running, and then removes only that project-scoped task. This ordering is deliberate because Microsoft documents that `schtasks /delete` removes the scheduled task but does not interrupt a program already running from that task. citeturn0search0turn0search9

The uninstall does not remove `.multiagentos/` project state.

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
| Restart after process exit | launchd KeepAlive | Not enabled by default |\n| Project-scoped identity | Yes | Yes |\n| Lifecycle targets only selected project | Yes | Yes |
| Status | `multiagentos mcp status` | `multiagentos mcp status` |
| Uninstall | `multiagentos mcp uninstall` | `multiagentos mcp uninstall` |

The managed-service implementation is intentionally OS-native: macOS uses launchd and Windows uses Task Scheduler.

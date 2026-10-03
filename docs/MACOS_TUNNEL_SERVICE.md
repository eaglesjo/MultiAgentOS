# macOS tunnel-client Service

MultiAgentOS can run the OpenAI `tunnel-client` as a **project-scoped** per-user
macOS `launchd` service alongside the local MCP service.

The service identity is derived deterministically from the canonical project
path:

```
project-id = SHA-256(canonical_project_root)[:12]

multiagentos.tunnel.project.<project-id>
```

This is the same project identity used by the project-scoped MCP service:

```
multiagentos.mcp.project.<project-id>
```

A project therefore owns both local services independently. Installing,
restarting, or removing one project's tunnel service must not affect another
project's tunnel or MCP service.

The current supported tunnel-client release path documents `tunnel-client run`
as the daemon process and recommends `MCP_STARTUP_WAIT_TIMEOUT` when the local
HTTP MCP listener may start after the client. MultiAgentOS uses that startup
guard and lets launchd own process restart/relaunch.

## Architecture

```
macOS user login
      |
      +--> launchd
      |      |
      |      +--> Project A MCP
      |      |      multiagentos.mcp.project.<A-ID>
      |      |
      |      +--> Project A tunnel-client
      |             multiagentos.tunnel.project.<A-ID>
      |
      +--> Project B MCP
      |      multiagentos.mcp.project.<B-ID>
      |
      +--> Project B tunnel-client
             multiagentos.tunnel.project.<B-ID>
```

The OpenAI tunnel service remains OpenAI-hosted. MultiAgentOS only manages the
local MCP server and local `tunnel-client` process.

## Project-scoped identity

The installer accepts the project root explicitly:

```bash
bash scripts/macos/install_tunnel_client_launchd.sh \
  --path /absolute/path/to/project
```

The installer canonicalizes that path and derives the project ID automatically.
No manual service ID is required.

Inspect the same MCP project identity with:

```bash
python3 -c '
from pathlib import Path
from multiagentos.mcp_service import _service_id, _service_label
p = Path("/absolute/path/to/project").resolve()
print("Project Root :", p)
print("Project ID   :", _service_id(p))
print("MCP Label    :", _service_label(p))
print("Tunnel Label :", f"multiagentos.tunnel.project.{_service_id(p)}")
'
```

Each project gets its own:

- launchd label
- LaunchAgent plist
- wrapper script
- log files
- Keychain service name

## Security model

The Runtime API key is stored in the **macOS Keychain** under a
project-scoped service name:

```
multiagentos.tunnel.project.<project-id>.runtime-key
```

The key is not written to:

- the Git repository
- the launchd plist
- the generated wrapper command line
- MultiAgentOS project configuration

The wrapper retrieves the key from Keychain at process startup and exposes it
only to `tunnel-client` through `CONTROL_PLANE_API_KEY`.

The Runtime API key should remain a restricted key with Tunnels Read + Use.
Do not use an admin key for this service.

## Install

The MultiAgentOS MCP launchd service should already be installed for the same
project:

```bash
multiagentos mcp install \
  --path /absolute/path/to/project \
  --port 8000
```

Export the tunnel values in the installation shell:

```bash
export CONTROL_PLANE_TUNNEL_ID="tunnel_..."
export CONTROL_PLANE_API_KEY="..."
export MCP_SERVER_URL="http://127.0.0.1:8000/mcp"
```

Then install the project-scoped tunnel service:

```bash
bash scripts/macos/install_tunnel_client_launchd.sh \
  --path /absolute/path/to/project
```

If `tunnel-client` is not on PATH:

```bash
TUNNEL_CLIENT_BIN="/absolute/path/to/tunnel-client" \
  bash scripts/macos/install_tunnel_client_launchd.sh \
  --path /absolute/path/to/project
```

### Multiple projects

Each simultaneously running tunnel-client needs its own local health
listener. For example:

Project A:

```bash
MCP_SERVER_URL="http://127.0.0.1:8000/mcp" \
HEALTH_LISTEN_ADDR="127.0.0.1:18080" \
bash scripts/macos/install_tunnel_client_launchd.sh \
  --path /absolute/path/to/project-a
```

Project B:

```bash
MCP_SERVER_URL="http://127.0.0.1:8001/mcp" \
HEALTH_LISTEN_ADDR="127.0.0.1:18081" \
bash scripts/macos/install_tunnel_client_launchd.sh \
  --path /absolute/path/to/project-b
```

Do not reuse the same local health address for simultaneously running
tunnel-client services.

## Startup ordering

Both MCP and tunnel services use `RunAtLoad` and `KeepAlive`.

The tunnel client also uses:

```
MCP_STARTUP_WAIT_TIMEOUT=60s
```

This is specifically intended for an HTTP MCP listener that may come up after
the tunnel client. During this window, the client waits for the MCP listener
before its first poll/discovery attempt.

## Verify

Calculate the expected project-scoped label:

```bash
python3 -c '
from pathlib import Path
from multiagentos.mcp_service import _service_id
p = Path("/absolute/path/to/project").resolve()
print(f"multiagentos.tunnel.project.{_service_id(p)}")
'
```

Then inspect it:

```bash
launchctl print \
  "gui/$(id -u)/multiagentos.tunnel.project.<project-id>"
```

Check tunnel-client readiness using the project's configured health address:

```bash
curl -fsS http://127.0.0.1:18080/readyz
```

Check detailed health:

```bash
curl -fsS 'http://127.0.0.1:18080/health?details=true'
```

The tunnel-client documentation treats `/readyz` as the primary local
readiness signal; `control_plane_poll_health` is a separate component and
should be inspected independently.

## Logs

Logs remain inside the project that owns the service:

```
<project>/.multiagentos/logs/tunnel-client-launchd.log
<project>/.multiagentos/logs/tunnel-client-launchd.error.log
<project>/.multiagentos/logs/tunnel-client.log
```

## Stop / remove

Remove only the selected project's service:

```bash
PROJECT_ID="$(
  python3 -c '
from pathlib import Path
import hashlib
p = Path("/absolute/path/to/project").expanduser().resolve()
print(hashlib.sha256(str(p).encode("utf-8")).hexdigest()[:12])
'
)"

LABEL="multiagentos.tunnel.project.$PROJECT_ID"

launchctl bootout "gui/$(id -u)/$LABEL" || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
rm -f "/absolute/path/to/project/.multiagentos/tunnel-client-launchd.sh"
```

Remove the selected project's Runtime API key from Keychain when it is no
longer needed:

```bash
security delete-generic-password \
  -a "$USER" \
  -s "multiagentos.tunnel.project.<project-id>.runtime-key"
```

These operations do not target another project's service.

## Legacy global service

Older installations may still have the legacy global service:

```
com.eaglesjo.multiagentos.tunnel-client
```

The project-scoped installer does **not** automatically remove that service.
This avoids unexpectedly stopping an existing deployment during migration.

For a migration, first verify the project-scoped service is healthy, then
remove the legacy service explicitly if it is no longer needed.

## Important runtime rule

Do not run both:

1. a `tunnel-client runtimes connect` managed runtime for the same deployment,
2. and a launchd `tunnel-client run` service,

at the same time unless you intentionally want multiple HTTP runtime replicas.

The native `runtimes connect` flow is the official managed runtime lifecycle
surface. The launchd integration here is specifically for macOS login/reboot
process ownership.

## Operational target

After a reboot or user login:

```
launchd
  |
  +--> Project MCP
  |      :8000
  |
  +--> Project tunnel-client
         :18080/readyz
         |
         v
     OpenAI Secure MCP Tunnel
```

For another project, use another MCP port and another local tunnel health
port. This allows multiple project-scoped MCP + tunnel pairs to coexist on the
same macOS user session.

# macOS tunnel-client Service

MultiAgentOS can run the OpenAI `tunnel-client` as a per-user macOS `launchd`
service alongside the local MCP service.

The current supported tunnel-client release path documents `tunnel-client run`
as the daemon process and recommends `MCP_STARTUP_WAIT_TIMEOUT` when the local
HTTP MCP listener may start after the client. MultiAgentOS uses that startup
guard and lets launchd own process restart/relaunch. citeturn3search0

## Architecture

```
macOS user login
      |
      +--> launchd
      |      |
      |      +--> MultiAgentOS MCP :8000
      |      |
      |      +--> tunnel-client :18080 health
      |               |
      |               v
      |        OpenAI Secure MCP Tunnel
      |
      v
  local project
```

The OpenAI tunnel service remains OpenAI-hosted. MultiAgentOS only manages the
local MCP server and local `tunnel-client` process.

## Security model

The Runtime API key is stored in the **macOS Keychain** under:

```
com.eaglesjo.multiagentos.tunnel-client.runtime-key
```

The key is not written to:

- the Git repository
- the launchd plist
- the generated wrapper command line
- MultiAgentOS project configuration

The wrapper retrieves the key from Keychain at process startup and exposes it
only to `tunnel-client` through `CONTROL_PLANE_API_KEY`.

The Runtime API key should remain a restricted key with Tunnels Read + Use.
Do not use an admin key for this service. citeturn1search2

## Install

The MultiAgentOS MCP launchd service should already be installed:

```bash
bash scripts/macos/install_mcp_launchd.sh --allow-write
```

Export the existing tunnel values in the installation shell:

```bash
export CONTROL_PLANE_TUNNEL_ID="tunnel_..."
export CONTROL_PLANE_API_KEY="..."
export MCP_SERVER_URL="http://127.0.0.1:8000/mcp"
```

Then install the tunnel service:

```bash
bash scripts/macos/install_tunnel_client_launchd.sh
```

If `tunnel-client` is not on PATH:

```bash
TUNNEL_CLIENT_BIN="/absolute/path/to/tunnel-client" \
  bash scripts/macos/install_tunnel_client_launchd.sh
```

The installer writes a per-user LaunchAgent and stores the Runtime API key in
Keychain.

## Startup ordering

Both services use `RunAtLoad` and `KeepAlive`.

The tunnel client also uses:

```
MCP_STARTUP_WAIT_TIMEOUT=60s
```

This is specifically intended for an HTTP MCP listener that may come up after
the tunnel client. During this window, the client waits for the MCP listener
before its first poll/discovery attempt. citeturn3search0

## Verify

Check the service:

```bash
launchctl print gui/$(id -u)/com.eaglesjo.multiagentos.tunnel-client
```

Check tunnel-client readiness:

```bash
curl -fsS http://127.0.0.1:18080/readyz
```

Check detailed health:

```bash
curl -fsS 'http://127.0.0.1:18080/health?details=true'
```

The tunnel-client documentation treats `/readyz` as the primary local
readiness signal; `control_plane_poll_health` is a separate component and
should be inspected independently. citeturn0search7

## Logs

```
.multiagentos/logs/tunnel-client-launchd.log
.multiagentos/logs/tunnel-client-launchd.error.log
.multiagentos/logs/tunnel-client.log
```

## Stop / remove

```bash
launchctl bootout gui/$(id -u)/com.eaglesjo.multiagentos.tunnel-client
rm -f ~/Library/LaunchAgents/com.eaglesjo.multiagentos.tunnel-client.plist
rm -f scripts/macos/run_tunnel_client_launchd.sh
```

To remove the stored Runtime API key from Keychain:

```bash
security delete-generic-password \
  -a "$USER" \
  -s "com.eaglesjo.multiagentos.tunnel-client.runtime-key"
```

## Important runtime rule

Do not run both:

1. a `tunnel-client runtimes connect` managed runtime for the same deployment,
2. and this launchd `tunnel-client run` service,

at the same time unless you intentionally want multiple HTTP runtime replicas.

For the MultiAgentOS single-host deployment, use **one local tunnel-client
supervisor**. The native `runtimes connect` flow is the official managed
runtime lifecycle surface; the launchd integration here is specifically for
macOS login/reboot process ownership. citeturn0search2turn1search3

## Operational target

After a reboot or user login:

```
launchd
  |
  +--> MultiAgentOS MCP
  |      :8000
  |
  +--> tunnel-client
         :18080/readyz
         |
         v
     OpenAI Secure MCP Tunnel
```

This removes the need to manually start either local process.

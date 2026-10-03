# macOS project-scoped tunnel-client Service

MultiAgentOS can run OpenAI's `tunnel-client` as a per-user macOS `launchd`
service for each local project. The service identity is derived from the
canonical project path, so multiple projects can coexist without sharing a
launchd label, wrapper, log directory, or Keychain entry.

## Architecture

```
Project A MCP :8002  <-- Tunnel A --> OpenAI Secure MCP Tunnel
Project B MCP :8003  <-- Tunnel B --> OpenAI Secure MCP Tunnel
Project C MCP :8004  <-- Tunnel C --> OpenAI Secure MCP Tunnel
```

Each tunnel must point at the exact MCP endpoint belonging to its project.
The MCP target is never inferred from a global/default port.

Each project also needs a unique local health address because the
`tunnel-client` health listener is local to the machine.

## Install

The project MCP service should already be running.

For PetTarotReading:

```bash
export CONTROL_PLANE_TUNNEL_ID="tunnel_..."
export CONTROL_PLANE_API_KEY="..."

bash scripts/macos/install_tunnel_client_launchd.sh \
  --path /Volumes/DevFiles/DevProjects/AppProjests/PetTarotReading \
  --mcp-server-url http://127.0.0.1:8003/mcp \
  --health-listen-addr 127.0.0.1:18081
```

For another project, use that project's MCP endpoint and a different health
port.

The Runtime API key is stored in the macOS Keychain and is not written to the
launchd plist or generated wrapper.

## Project identity

For a project root, MultiAgentOS derives:

```
SHA256(canonical_project_path)[:12]
```

and uses it for:

```
multiagentos.tunnel.project.<project-id>
```

The generated wrapper and logs live under:

```
<project>/.multiagentos/
```

The Keychain service is also project-scoped.

## Startup lifecycle

The installer first boots out the previous service for the selected project,
waits for launchd to report that it is unloaded, then bootstraps and kickstarts
the new service. This avoids a stale launchd registration causing
`bootstrap failed: 5` during reinstall.

## Verify

For a project whose label is `multiagentos.tunnel.project.<project-id>`:

```bash
launchctl print gui/$(id -u)/multiagentos.tunnel.project.<project-id>
curl -fsS http://127.0.0.1:18081/readyz
```

The tunnel-client also exposes local health/readiness surfaces. Use
`/readyz` as the readiness gate before testing the OpenAI-side connection.

## Logs

Each project keeps:

```
<project>/.multiagentos/logs/tunnel-client-launchd.log
<project>/.multiagentos/logs/tunnel-client-launchd.error.log
<project>/.multiagentos/logs/tunnel-client.log
```

## Remove

```bash
bash scripts/macos/uninstall_tunnel_client_launchd.sh \
  --path /Volumes/DevFiles/DevProjects/AppProjests/PetTarotReading
```

Add `--delete-keychain` when the project's stored Runtime API key should also
be removed.

## Operational rule

Do not run two tunnel clients for the same tunnel/project unless you
intentionally want multiple replicas. Separate projects should use separate
project-scoped services and point each service at its own private MCP endpoint.

# macOS project-scoped tunnel-client service

MultiAgentOS manages one OpenAI `tunnel-client` launchd service per local
project. Each service has a project-derived launchd label, wrapper, log
directory, and Keychain identity.

## Multi-project topology

```
MultiAgentOS       MCP :8002  <- Tunnel A -> OpenAI Secure MCP Tunnel
PetTarotReading    MCP :8003  <- Tunnel B -> OpenAI Secure MCP Tunnel
Project C          MCP :8004  <- Tunnel C -> OpenAI Secure MCP Tunnel
```

A tunnel must point to the exact MCP endpoint belonging to its project. There
is no default `:8000/mcp` target.

Each tunnel also needs a unique local health address.

## Install PetTarotReading tunnel

```bash
export CONTROL_PLANE_TUNNEL_ID="tunnel_..."
export CONTROL_PLANE_API_KEY="..."

bash scripts/macos/install_tunnel_client_launchd.sh \
  --path /Volumes/DevFiles/DevProjects/AppProjests/PetTarotReading \
  --mcp-server-url http://127.0.0.1:8003/mcp \
  --health-listen-addr 127.0.0.1:18081
```

For MultiAgentOS itself use its own project path, `http://127.0.0.1:8002/mcp`,
and another health address such as `127.0.0.1:18080`.

Every additional project gets its own MCP endpoint, project-derived launchd
label, and unique health address.

## Project identity

The canonical project path is hashed as:

```
SHA256(canonical_project_path)[:12]
```

The result determines `multiagentos.tunnel.project.<project-id>`. The wrapper
and logs live under `<project>/.multiagentos/`, and the Runtime API key is
stored in the macOS Keychain under the same project-scoped identity.

## Reinstall lifecycle

The installer boots out the selected project's previous service, waits until
launchd reports that it is unloaded, then bootstraps and kickstarts the new
service. This avoids stale-registration errors such as `bootstrap failed: 5`.

## Verify

```bash
launchctl print gui/$(id -u)/multiagentos.tunnel.project.<project-id>
curl -fsS http://127.0.0.1:18081/readyz
```

OpenAI's Secure MCP Tunnel exposes `/readyz` as a local readiness surface;
the client must be healthy and running before testing the OpenAI-side MCP
connection.

## Remove

```bash
bash scripts/macos/uninstall_tunnel_client_launchd.sh \
  --path /Volumes/DevFiles/DevProjects/AppProjests/PetTarotReading
```

Use `--delete-keychain` when the project's stored Runtime API key should
also be removed.

## Logs

Each project has its own tunnel-client launchd stdout, stderr, and client logs
under `<project>/.multiagentos/logs/`.

Do not run two tunnel clients for the same tunnel/project unless multiple
replicas are intentional.

# Agent Execution Runtime MCP Architecture Decision

## Status

**Accepted — architecture is locked unless explicitly changed by a future architecture decision.**

This document records the Agent Execution Runtime MCP boundary so work can resume consistently after a conversation/session disconnect.

## Non-negotiable architecture

**The Agent Execution Runtime has one MCP Server.**

The OpenAI Secure MCP Tunnel and `tunnel-client` are transport/connection infrastructure. They are **not a second Agent Execution Runtime MCP Server** and must not be modeled as an additional MCP layer.

### Local/free path

```text
MCP Client
    |
    | MCP / stdio
    v
Agent Execution Runtime MCP Server
    |
    v
Local Project
```

The Agent Execution Runtime MCP Server must remain independently usable without OpenAI, ChatGPT, a ChatGPT subscription, a `tunnel_id`, or `tunnel-client`.

### OpenAI-connected local path

```text
ChatGPT / Codex
    |
    | MCP
    v
OpenAI Secure MCP Tunnel
    |
    v
tunnel-client
    |
    | stdio or HTTP
    v
Agent Execution Runtime MCP Server
    |
    v
Local Project
```

The same Agent Execution Runtime MCP Server is used in both paths.

## Responsibilities

| Component | Responsibility |
| --- | --- |
| ChatGPT / Codex | MCP client / coding agent |
| GitHub Connector / GitHub | Remote repository and GitHub resources |
| Secure MCP Tunnel | Private OpenAI-to-local transport |
| `tunnel-client` | Tunnel-side request forwarding |
| **Agent Execution Runtime MCP Server** | **Actual MCP server and local tool boundary** |
| Local project | Filesystem, Git, process and project resources |

## Product principle

The Agent Execution Runtime MCP Server is a **free, standalone MCP capability**.

OpenAI Secure MCP Tunnel is an **optional integration path**, not a prerequisite for Agent Execution Runtime MCP.

Therefore:

- Do not make OpenAI credentials mandatory for local Agent Execution Runtime MCP.
- Do not duplicate MCP server implementations merely for tunnel usage.
- Do not describe `tunnel-client` as an MCP server.
- Do not make the Agent Execution Runtime MCP core depend on ChatGPT or Codex.
- Keep the MCP server transport-independent so other MCP clients can use it.

## Current implementation baseline

The repository already contains the stdio Agent Execution Runtime MCP server and its CI/install-smoke coverage.

The next validation work is:

1. Validate a real non-OpenAI MCP client against the free local Agent Execution Runtime MCP Server.
2. Validate `initialize`, `tools/list`, and `filesystem.read`.
3. Validate write/process policy boundaries.
4. Separately validate the optional OpenAI Secure MCP Tunnel path.
5. Validate ChatGPT/Codex access through the tunnel without changing the Agent Execution Runtime MCP Server itself.

## GitHub and local development model

The intended development workflow has two independent resource paths:

```text
ChatGPT / Codex
    |
    +--> GitHub Connector / GitHub
    |       |
    |       +--> repository / PR / issue / remote artifacts
    |
    +--> Agent Execution Runtime MCP
            |
            +--> Secure MCP Tunnel (optional)
            |
            +--> local project
                    |
                    +--> files
                    +--> Git
                    +--> process
```

GitHub access and local-machine access are therefore complementary, not interchangeable.

## Change control

This architecture is considered **locked**. Any change to the following requires an explicit architecture decision:

- the number of Agent Execution Runtime MCP server boundaries;
- the role of Secure MCP Tunnel;
- the role of `tunnel-client`;
- the requirement that Agent Execution Runtime MCP remain independently/free locally usable;
- the separation between GitHub access and local-machine access.

OpenAI Secure MCP Tunnel currently forwards MCP JSON-RPC requests from the OpenAI-hosted tunnel endpoint through `tunnel-client` to a private MCP server; the private MCP server remains inside the user's network. This confirms that the tunnel is a transport path rather than a second Agent Execution Runtime MCP server.


## Terminology migration

The canonical architectural role is **Agent Execution Runtime**. See [Terminology](TERMINOLOGY.md).


## MCP durable recovery contract

The Agent Execution Runtime MCP server exposes durable recovery through the `runtime/recover` JSON-RPC method.

### Request

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "method": "runtime/recover",
  "params": {
    "workUnitId": "work-unit-id"
  }
}
```

`sessionId` may also be supplied when recovery must be associated with an existing MCP session.

### Response

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "result": {
    "workUnitId": "work-unit-id",
    "disposition": "completed",
    "replayed": true,
    "invocationId": "invocation-id",
    "idempotencyKey": "idempotency-key"
  }
}
```

Recovery is durable and idempotent:

- A safe read-only invocation interrupted after the durable `STARTED` boundary may be replayed with the original invocation and idempotency identity.
- A completed work unit is not replayed again; the response reports `replayed: false`.
- Side-effecting invocations are not automatically replayed after a crash. They resolve to `review_required` and require an explicit human decision.
- Recovery state and decisions remain under the project's durable `.multiagentos/` state boundary.

This contract is intentionally separate from `tools/call`: normal tool invocation records durable execution evidence, while `runtime/recover` explicitly requests reconciliation of an interrupted work unit.

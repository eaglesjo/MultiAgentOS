# MultiAgentOS Terminology

## Status

**Accepted — terminology baseline for the current architecture.**

This document defines the public architectural names used by MultiAgentOS. Existing implementation identifiers may remain temporarily for compatibility.

## Canonical names

| Term | Canonical meaning |
| --- | --- |
| **MultiAgentOS** | The complete multi-agent development orchestration platform |
| **Orchestrator** | Top-level collaboration and workflow coordination boundary |
| **MultiAgentWorkflow** | Concrete multi-stage Developer → Tester → Reviewer workflow |
| **Agent Execution Runtime** | Local execution, permission, tool, and verification boundary used by agents |
| **ChatGPT Web** | Sole user-facing entry point in the current reference architecture |
| **ChatGPT Codex Connector** | Remote GitHub repository access path |
| **Agent Execution Runtime MCP Server** | The MCP server exposing the local execution boundary |
| **Secure MCP Tunnel** | Optional transport path between an OpenAI-hosted client and the local MCP server |
| **tunnel-client** | Tunnel-side transport/forwarding process; not an MCP server |
| **MultiAgentRuntime** | Existing application/runtime adapter API; it is not the top-level orchestration boundary |
| **ChatAgentBridge** | Bridge from a Chat Agent turn into the orchestration/execution lifecycle |
| **VYRELON** | Legacy/compatibility implementation identifier retained where existing package, integration, protocol, or historical names require it |

## Naming rule

New architecture documentation should use **Agent Execution Runtime** instead of **VYRELON** when describing the role.

Use **VYRELON** only when referring to an existing implementation identifier, compatibility surface, protocol/namespace, historical document, or migration target.

Examples:

- Prefer: **Agent Execution Runtime MCP Server**
- Prefer: **Agent Execution Runtime execution boundary**
- Avoid introducing: **VYRELON as the MultiAgentOS product name**
- Avoid describing: Secure MCP Tunnel as a second MCP server

## Responsibility boundary

```text
ChatGPT Web
    |
    +--> ChatGPT Codex Connector --> GitHub Repository
    |
    +--> Agent Execution Runtime MCP / Secure MCP Tunnel
                                      |
                                      v
                              Agent Execution Runtime
                                      |
                                      v
                                Local Project
                                      |
                                      v
                                 MultiAgentOS
                                      |
                                      v
                                  Orchestrator
                                      |
                                      v
                              MultiAgentWorkflow
                               /      |       \
                         Developer   Tester   Reviewer
                                      |
                                      v
                                 Verification
```

The Agent Execution Runtime owns the execution authority. Agents and orchestration components provide intent, plans, assignments, and results; they do not bypass the runtime's permission and execution boundary.

## Compatibility policy

This terminology change is intentionally descriptive-first.

Existing Python modules, package metadata, IDE namespaces, MCP configuration keys, and document filenames containing `vyrelon` are not renamed in this pass. They can be migrated separately after consumers and tests are identified.

The public architecture should therefore be understandable without knowing the historical VYRELON name.

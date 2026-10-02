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
| **ChatGPT Web** | Verified full development entry point in the current setup: GitHub + local MCP |
| **ChatGPT Mobile App** | Verified GitHub-only development entry point in the current setup | 
| **ChatGPT Codex Connector** | Remote GitHub repository access path |
| **Agent Execution Runtime MCP Server** | The MCP server exposing the local execution boundary |
| **Secure MCP Tunnel** | Optional transport path between an OpenAI-hosted client and the local MCP server |
| **tunnel-client** | Tunnel-side transport/forwarding process; not an MCP server |
| **MultiAgentRuntime** | Existing application/runtime adapter API; it is not the top-level orchestration boundary |
| **ChatAgentBridge** | Bridge from a Chat Agent turn into the orchestration/execution lifecycle |

## Naming rule



Examples:

- Prefer: **Agent Execution Runtime MCP Server**
- Prefer: **Agent Execution Runtime execution boundary**
- Avoid describing: Secure MCP Tunnel as a second MCP server

## Responsibility boundary

```text
ChatGPT Web
    |
    +--> ChatGPT Codex Connector --> GitHub Repository
    |
    +--> Agent Execution Runtime MCP --> Local Project

ChatGPT Mobile App
    |
    +--> ChatGPT Codex Connector --> GitHub Repository
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

In the verified current setup, ChatGPT Web can use both the GitHub and local MCP paths, while ChatGPT Mobile uses the GitHub path only. The Agent Execution Runtime owns the execution authority. Agents and orchestration components provide intent, plans, assignments, and results; they do not bypass the runtime's permission and execution boundary.

## Compatibility policy

This terminology change is intentionally descriptive-first.



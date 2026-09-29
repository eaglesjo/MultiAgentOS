# MultiAgentOS

> **Cost-Free Multi-Agent Development Orchestration**

MultiAgentOS is a local-first development orchestration platform built around **VYRELON**.

The cost-free baseline does **not require a separate paid AI API key**. MultiAgentOS connects an already-available AI client with GitHub and a local project while keeping execution authority inside VYRELON.

## Why MultiAgentOS

MultiAgentOS separates **AI collaboration** from **execution authority**.

- **ChatGPT Web** — single user-facing entry point
- **ChatGPT Codex Connector** — remote GitHub repository access
- **VYRELON MCP / Secure Tunnel** — local project access
- **Orchestrator** — top-level multi-agent coordination
- **MultiAgentWorkflow** — concrete Developer → Tester → Reviewer execution
- **VYRELON** — permission and execution authority

Agents provide intent, plans, and results. They do not directly own filesystem, process, patch, or Git execution authority.

## Architecture

```text
                         Web Browser
                              |
                              v
                         ChatGPT Web
                              |
                    +---------+---------+
                    |                   |
                    v                   v
       ChatGPT Codex Connector       VYRELON
                    |                MCP / Secure Tunnel
                    v                   |
            GitHub Repository            v
                                  Local Project
                    |                   |
                    +---------+---------+
                              |
                              v
                        MultiAgentOS
                              |
                              v
                         Orchestrator
                              |
                              v
                    MultiAgentWorkflow
                     /       |       \
               Developer   Tester   Reviewer
                              |
                              v
                         Verification
                              |
                              v
                           VYRELON
```

### Responsibility boundaries

| Component | Responsibility |
| --- | --- |
| **ChatGPT Web** | User-facing entry point |
| **ChatGPT Codex Connector** | Remote GitHub repository access |
| **VYRELON MCP / Secure Tunnel** | Local project connection |
| **MultiAgentOS** | Agent contracts, routing, state, and orchestration |
| **Orchestrator** | Overall collaboration coordination |
| **MultiAgentWorkflow** | Stage, handoff, review, and rework semantics |
| **VYRELON** | Permission and execution authority |

## Multi-agent workflow

```text
Request
  |
  v
Orchestrator
  |
  v
MultiAgentWorkflow
  |
  +--> Developer
  |
  +--> Tester
  |
  +--> Reviewer
  |
  +--> Rework when required
  |
  v
Verification
  |
  v
Completed / Failed
```

`Orchestrator.run_workflow()` is the stable higher-level orchestration entry point. `MultiAgentWorkflow` owns the concrete stage, handoff, review, and rework semantics. `MultiAgentRuntime` remains an application/runtime adapter and delegates execution to the orchestration boundary.

VYRELON remains the execution boundary for permissions, filesystem access, patch application, process execution, Git operations, and verification.

## Connection model

### Remote GitHub path

```text
ChatGPT Web
    |
    v
ChatGPT Codex Connector
    |
    v
GitHub Repository
```

This path addresses the remote repository and its durable GitHub state.

### Local project path

```text
ChatGPT Web
    |
    v
VYRELON MCP / Secure Tunnel
    |
    v
VYRELON
    |
    v
Local Project
```

VYRELON has **one MCP Server**. Secure MCP Tunnel and `tunnel-client` are transport/connection infrastructure, not another MCP server.

The local VYRELON MCP server can be used independently without OpenAI, ChatGPT, a tunnel, or a paid AI API key.

## Cost-Free baseline

The core positioning is simple:

> **No separate paid AI API key is required for the MultiAgentOS cost-free baseline.**

The baseline also does not require:

- a separate agent API subscription
- a MultiAgentOS SaaS subscription
- a second MCP server for the tunnel path

AI-client/product plan limits still apply to the AI service you choose to use. “Cost-Free” describes the MultiAgentOS runtime architecture; it does not mean unlimited AI-service usage.

### Verified baseline capabilities

- VYRELON MCP stdio initialization and tool discovery
- filesystem READ / WRITE
- `patch.apply`
- `shell.run`
- local MCP/runtime tests
- runtime health/readiness
- Secure MCP Tunnel readiness

See [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md) for the verification record.

## Quick start

### Install

```bash
python -m pip install multiagentos
```

### Initialize a project

```bash
cd your-project
multiagentos init . --component all
multiagentos status .
```

### Run a local task

```bash
multiagentos run --path . --objective "run tests" -- python -m unittest discover -s tests -v
```

### Start a Chat Agent session

```bash
multiagentos chat --path . --objective "inspect the current project"
```

### Expose the VYRELON MCP server

```bash
multiagentos mcp serve --path .
```

For explicit filesystem writes and process execution:

```bash
multiagentos mcp serve \
  --path . \
  --allow-write \
  --allow-process
```

## Configuration

Project configuration is stored under `.multiagentos/`.

The initializer can install:

- `components.json` — selected components
- `execution.json` — execution Agent/Model selection
- `chat.json` — Chat Agent selection
- `agents.json` — multi-agent catalog
- `state/` and session/checkpoint data as applicable

Credentials and provider API keys are not written to project configuration.

## Validation

Run the local test suite:

```bash
python -m unittest discover -s tests -v
```

GitHub Actions validates the repository through CI.

## Documentation

- [Getting Started](docs/GETTING_STARTED.md)
- [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md)
- [VYRELON Connection Guide](docs/VYRELON_CONNECTIONS.md)
- [Secure MCP Tunnel Setup](docs/MCP_TUNNEL.md)
- [VYRELON GitHub Connection](docs/VYRELON_GITHUB_CONNECTION.md)
- [VYRELON MCP Architecture](docs/ARCHITECTURE_DECISIONS.md)

The English README is the canonical technical document. Localized READMEs preserve the same architecture, terminology, and cost-free baseline.

**[한국어](README.ko.md) · [日本語](README.ja.md) · [简体中文](README.zh-CN.md)**

## License

See [LICENSE](LICENSE).

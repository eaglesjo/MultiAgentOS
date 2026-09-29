# MultiAgentOS

> **Cost-Free Multi-Agent Development Orchestration**

MultiAgentOS is a local-first development orchestration platform built around **VYRELON**.

The cost-free baseline does **not require a separate paid AI API key**. MultiAgentOS orchestrates an already-available AI client together with GitHub and a local project, while keeping execution authority inside VYRELON.

## What it provides

- **ChatGPT Web as the single user entry point**
- **ChatGPT Codex Connector** for the remote GitHub repository path
- **VYRELON MCP / Secure Tunnel** for the local project path
- **Orchestrator** as the top-level multi-agent coordination boundary
- **MultiAgentWorkflow** for concrete Developer → Tester → Reviewer execution
- verification, handoff, review and bounded rework
- policy-controlled filesystem, patch, process and Git capabilities
- provider-neutral Agent and Model contracts
- durable WorkUnit state and workflow checkpoints

> **Cost-Free baseline**
>
> No separate paid AI API key, separate agent API subscription, or MultiAgentOS SaaS subscription is required for the baseline runtime.
>
> This describes the MultiAgentOS runtime cost model; AI-client/product plan limits still apply to the AI service you choose to use.

## Architecture

`text
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
                     /       |       \\
               Developer   Tester   Reviewer
                              |
                              v
                         Verification
                              |
                              v
                           VYRELON
`

The boundaries are intentional:

| Boundary | Responsibility |
| --- | --- |
| **ChatGPT Web** | User-facing entry point |
| **ChatGPT Codex Connector** | Remote GitHub repository access |
| **VYRELON MCP / Secure Tunnel** | Local project connection |
| **MultiAgentOS** | Agent contracts, routing and orchestration |
| **Orchestrator** | Overall collaboration coordination |
| **MultiAgentWorkflow** | Stage, handoff, review and rework semantics |
| **VYRELON** | Permission and execution authority |

Agents provide intent, plans and results. They do not directly own filesystem, process or Git execution authority.

## Multi-agent workflow

`text
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
`

`Orchestrator.run_workflow()` is the higher-level entry point. `MultiAgentWorkflow` owns the concrete stage and handoff semantics. `MultiAgentRuntime` is an application/runtime adapter and delegates execution to that orchestration boundary.

VYRELON remains the execution boundary: permissions, filesystem access, patch application, process execution, Git operations and verification are controlled there.

## Connection model

MultiAgentOS uses two complementary resource paths.

### Remote GitHub path

`text
ChatGPT Web
    |
    v
ChatGPT Codex Connector
    |
    v
GitHub Repository
`

This path addresses the remote repository and its durable GitHub state.

### Local project path

`text
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
`

VYRELON has **one MCP Server**. Secure MCP Tunnel and `tunnel-client` are transport/connection infrastructure, not another MCP server.

The local VYRELON MCP server is independently usable without OpenAI, ChatGPT, a tunnel ID, or a paid AI API key.

## Cost-Free baseline

The baseline acceptance path is:

`text
Install MultiAgentOS
        |
        v
Initialize project
        |
        v
VYRELON MCP
        |
        +--> filesystem READ
        +--> filesystem WRITE / PATCH
        +--> process / test execution
        |
        v
AI client
`

The verified baseline includes:

- VYRELON MCP stdio initialization and tool discovery
- filesystem WRITE/READ
- `patch.apply`
- `shell.run`
- local MCP/runtime tests
- local runtime health/readiness
- Secure MCP Tunnel readiness

See [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md) for the verification record.

## CLI

Install from PyPI:

`bash
python -m pip install multiagentos
`

Initialize a project:

`bash
cd your-project
multiagentos init . --component all
multiagentos status .
`

Run a local task through the VYRELON lifecycle:

`bash
multiagentos run --path . --objective "run tests" -- python -m unittest discover -s tests -v
`

Use the Chat Agent:

`bash
multiagentos chat --path . --objective "inspect the current project"
`

Expose the local VYRELON MCP server:

`bash
multiagentos mcp serve --path .
`

For explicit local writes and process execution:

`bash
multiagentos mcp serve \
  --path . \
  --allow-write \
  --allow-process
`

Install the multi-agent component independently when needed:

`bash
multiagentos init . --component multi-agent
`

Initialize both VYRELON and multi-agent components:

`bash
multiagentos init . --component all
`

## Configuration

Project configuration is stored under `.multiagentos/`.

The initializer can install:

- `components.json` — selected components
- `execution.json` — execution Agent/Model selection
- `chat.json` — Chat Agent selection
- `agents.json` — multi-agent catalog
- `state/` and session/checkpoint data as applicable

Credentials and provider API keys are not written to the project configuration.

## Validation

Run the local test suite:

`bash
python -m unittest discover -s tests -v
`

GitHub Actions validates the repository through CI.

## Documentation

- [Getting Started](docs/GETTING_STARTED.md)
- [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md)
- [VYRELON Connection Guide](docs/VYRELON_CONNECTIONS.md)
- [Secure MCP Tunnel Setup](docs/MCP_TUNNEL.md)
- [VYRELON GitHub Connection](docs/VYRELON_GITHUB_CONNECTION.md)
- [VYRELON MCP Architecture](docs/ARCHITECTURE_DECISIONS.md)

## Localization

The English README is the canonical technical document. Localized READMEs preserve the same architecture, terminology and cost-free baseline.

**[한국어](README.ko.md) · [日本語](README.ja.md) · [简体中文](README.zh-CN.md)**

## License

See [LICENSE](LICENSE).

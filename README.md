# MultiAgentOS

**A local-first, GitHub-native foundation for AI-assisted software development.**

MultiAgentOS is the foundation for **VYRELON**, a policy-controlled runtime and multi-agent development orchestrator. It connects conversational AI to a real project without collapsing the boundary between a remote GitHub repository and the developer's local workspace.

> **Two connections, two responsibilities**
> - **GitHub URL → ChatGPT GitHub app → remote GitHub repository**
> - **VYRELON → MCP / Secure MCP Tunnel → local project**
>
> These paths are complementary. The GitHub connection identifies and exposes the authorized remote repository; VYRELON provides the local filesystem, patch, process, and runtime boundary.

**Documentation:** [English](README.md) · [한국어](README.ko.md) · [日本語](README.ja.md) · [简体中文](README.zh-CN.md)

## Core principles

- Local-first: filesystem, shell, processes and Git are first-class.
- GitHub-native: repository, branch, commit, issue, pull request, review and CI lifecycle are first-class.
- Chat-Agent agnostic with ChatGPT as the default primary conversational agent; Gemini, Claude and other providers can participate.
- Multi-AI assignment: agents can use explicit, pool/fallback, or automatic model routing.
- Executable lifecycle: Understand -> Plan -> Delegate -> Execute -> Verify -> Review -> Handoff.
- Profile-driven: React Native, Android Native and iOS Native extend the common core.
- Policy-controlled writes: repository and GitHub mutations are explicit runtime capabilities.

## Current runtime

VYRELON currently includes:

- provider-neutral WorkUnit, Agent, Model, Runtime, Profile, and GitHub contracts
- deterministic multi-AI routing
- model adapters for generic CLI and HTTP JSON endpoints
- model-backed agent execution
- policy-controlled local process and GitHub runtimes
- evidence-based technology profile detection
- executable project bootstrap via the MultiAgentOS CLI
- explicit planning contracts and persistent WorkUnit state
- unified VYRELON runtime facade for project, Git, and GitHub control
- provider-neutral Chat Agent contracts and persistent VYRELON agent rules
- local stdlib unittest validation plus GitHub Actions CI
- read-only project status and durable checkpoint inspection
- project-scoped execution configuration for selecting the CLI Agent/Model
- direct project Chat Agent CLI with optional persistent conversation sessions
- provider capability discovery with OpenAI, Anthropic, and Gemini native defaults
- persistent model capability, quota, and health intelligence with cooldown-aware routing
- unified model control-plane inspection and provider-neutral routing explainability
- VYRELON stdio MCP server with read-only-by-default local tool exposure

## CLI

After installation:

    multiagentos detect .
    multiagentos init .
    multiagentos init . --component vyrelon
    multiagentos init . --component multi-agent
    multiagentos init . --component all
    multiagentos status .
    multiagentos run --path . --objective "run tests" -- python -m unittest discover -s tests -v
    multiagentos run --path . --agent custom-executor --model custom-process --objective "run tests" -- python -m unittest discover -s tests -v
    multiagentos resume <work-unit-id> --path .
    multiagentos chat --path . --objective "inspect the current project"
    multiagentos chat --path . --execute --objective "run the smoke test" -- python -m unittest discover -s tests -v
    multiagentos chat --path . --objective "continue our conversation" --session project-1
    multiagentos mcp serve --path .
    multiagentos mcp serve --path . --allow-write --allow-process
    python tests/mcp_stdio_smoke.py
    multiagentos github probe eaglesjo/MultiAgentOS
    multiagentos models discover .
    multiagentos models control .
    multiagentos models capabilities .
    multiagentos models quota .
    multiagentos models health .
    multiagentos models explain . --agent developer

The initializer supports independent installation:

- `vyrelon`: VYRELON runtime, policy, lifecycle, planning/state, project profile and execution configuration.
- `multi-agent`: role catalog and profile-specific multi-agent definitions.
- `all`: both components.

The selected mode is recorded in:

    .multiagentos/components.json

VYRELON installation also writes:

    .multiagentos/execution.json
    .multiagentos/chat.json

The default execution configuration is:

    {
      "version": 1,
      "runtime": "process",
      "agent_id": "cli-executor",
      "model_id": "local-process"
    }

The `run` and `resume` commands load Agent/Model IDs from this project configuration and resolve them through VYRELON's provider-neutral Agent/AI registries. `--agent` and `--model` are explicit per-invocation overrides. An unknown or incompatible Agent/Model pair is rejected instead of silently constructing a new execution contract. The runtime and process capability remain controlled by VYRELON; the configuration does not contain credentials or executable command definitions.

Multi-agent installation additionally writes:

    .multiagentos/agents.json

The project Chat Agent defaults to ChatGPT and is resolved through VYRELON's provider-neutral Chat Agent registry. Gemini, Claude, and other registered providers can be selected by changing `chat.json`; the selected Chat Agent still has no execution authority above VYRELON.

The `chat` command sends a conversational request through the configured Chat Agent and returns its summary, proposed plan steps, findings, artifacts, and provider evidence as JSON. It does not execute filesystem, Git, GitHub, process, verification, or review actions unless --execute is explicitly supplied with a user-provided command. In execution mode, the Chat Agent still only supplies intent/plan; VYRELON's configured execution Agent/Model owns the explicit command and lifecycle. Use `--session <id>` to persist conversation turns under `.multiagentos/sessions/`; credentials are never stored there. Provider SDKs remain optional and CI tests use injected adapters.

No provider credentials or API keys are written to the project.

The read-only `status` command reports installed components, detected profiles, execution configuration, agent catalog entries, WorkUnits, and durable workflow checkpoints. The `run` command executes a local command through the VYRELON WorkUnit lifecycle, while `resume` reloads a durable orchestration checkpoint and continues it. It makes interrupted or resumable work visible without granting the CLI any additional execution authority.

## Architecture

    Core Orchestration
        |
        +-- Agent Contracts
        +-- AI Routing
        +-- Lifecycle
        |
    Runtime Adapters
        |
        +-- Local Process
        +-- Model CLI
        +-- Model HTTP
        +-- GitHub
        +-- MCP Server
        |
    Technology Profiles
        |
        +-- React Native
        +-- Android Native
        +-- iOS Native

## Cost-free baseline

MultiAgentOS does not require a paid AI API key for its core local development path. The VYRELON MCP runtime provides local filesystem READ/WRITE, patch application, and process/test execution independently of a model-provider API.

The verified baseline is documented in [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md). The current VYRELON runtime, filesystem WRITE/READ, `patch.apply`, `shell.run`, and local MCP/runtime tests are verified. Secure MCP Tunnel is ready for remote MCP integration; ChatGPT Web write-capable MCP access remains plan-gated by OpenAI's current product availability.

## Validation

    python -m unittest discover -s tests -v

GitHub Actions runs the same test suite on pull requests and pushes.


### Chat Agent adapter resolution

VYRELON resolves the configured Chat Agent through a provider-neutral adapter registry:

    .multiagentos/chat.json
            |
            v
    ChatAgentRegistry
            |
            v
    ChatAdapterRegistry
            |
            +-- ChatGPT -> OpenAI adapter
            +-- Gemini -> provider adapter when registered
            +-- Claude -> provider adapter when registered

The core does not require a provider SDK. The OpenAI/ChatGPT adapter remains optional and obtains credentials from the provider's normal environment/authentication mechanism. A Chat Agent can propose intent and plans, but actual filesystem, Git, GitHub, process, verification, review, and approval actions remain VYRELON responsibilities.


## VYRELON MCP server

VYRELON can expose its local tool surface as a stdio MCP server:

    multiagentos mcp serve --path /path/to/project

The default surface is read-only. Filesystem write/patch tools require `--allow-write`, and shell execution requires `--allow-process`.

This server is intended to be launched locally by a transport such as OpenAI Secure MCP Tunnel; MultiAgentOS does not open a public inbound MCP port or provision the tunnel automatically.

## User setup and integrations

VYRELON is delivered as an installable local runtime. The MCP server remains free and independently usable; OpenAI Secure MCP Tunnel is an optional connection path.

### Install

From the MultiAgentOS checkout:

```bash
python -m pip install .
multiagentos --help
```

Initialize VYRELON in a project:

```bash
cd your-project
multiagentos init . --component all
multiagentos status .
```

### Connection model

VYRELON has **one MCP server**. GitHub access and local-machine access are complementary paths:

```text
                         +--> ChatGPT GitHub app --> GitHub
                        /
ChatGPT / Codex -------+
                        \
                         +--> Secure MCP Tunnel (optional)
                                  |
                                  v
                            tunnel-client
                                  |
                                  v
                         VYRELON MCP Server
                                  |
                                  v
                             Local Project
```

The GitHub connection does not expose the developer's local filesystem. The tunnel connection does not create another MCP server.

### Four practical paths

| Need | Connection |
| --- | --- |
| ChatGPT works on a remote repository | ChatGPT -> GitHub app -> authorized repository |
| VYRELON works with GitHub locally | VYRELON -> `gh` -> GitHub |
| Any MCP client uses VYRELON locally | MCP Client -> VYRELON MCP Server |
| ChatGPT/Codex uses the local project | ChatGPT/Codex -> Secure MCP Tunnel -> `tunnel-client` -> VYRELON MCP Server |

### ChatGPT + GitHub

The ChatGPT GitHub connection is a separate user/account integration from the VYRELON MCP server. It must be installed and authorized before a ChatGPT conversation can access the selected repositories. OpenAI currently documents this as the GitHub app/connector; the exact menu label can vary by ChatGPT surface and plan.

**Connect the GitHub app/connector:**

1. Open **ChatGPT -> Settings -> Apps** (some surfaces may still show **Plugins**).
2. Find **GitHub** and select **Connect/Install**.
3. Complete the GitHub authorization flow.
4. In GitHub, install/authorize the ChatGPT GitHub app and select the repositories ChatGPT is allowed to access.
5. Return to ChatGPT and verify that the GitHub connection is available.
6. In a conversation, reference the repository by name/URL and ask ChatGPT to inspect files, code, issues, or documentation.

For a newly created or private repository, repository access may need to be explicitly selected in the GitHub app settings. Organization owners may also need to approve the app. OpenAI notes that repository availability can take a few minutes after authorization.

The standard ChatGPT GitHub app is a **repository-reading/search connection**; it does not by itself provide GitHub write/push/PR mutation authority. Code generation and direct GitHub writes are handled by supported Codex workflows. VYRELON's local filesystem/process capabilities are a separate execution boundary.

Reference: [OpenAI — Connecting GitHub to ChatGPT](https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt).

Connect GitHub in ChatGPT Settings -> Apps, authorize the GitHub application, and grant access to the repositories that should be available.

Then use a normal ChatGPT conversation with the repository URL and development task. Repository-level `AGENTS.md` / Agent Skills guidance can be used alongside VYRELON; the project's own engineering instructions remain authoritative.

### Local VYRELON + GitHub

```bash
gh auth login
gh auth status
multiagentos github probe OWNER/REPOSITORY
```

GitHub mutations remain controlled by VYRELON policy and approval.

### Local VYRELON MCP

```bash
multiagentos mcp serve --path /absolute/path/to/project
```

The default MCP surface is read-only. Write and process capabilities require explicit flags:

```bash
multiagentos mcp serve \
  --path /absolute/path/to/project \
  --allow-write \
  --allow-process
```

No OpenAI account, `tunnel_id`, or `tunnel-client` is required for the standalone MCP path.

### ChatGPT/Codex + local VYRELON

The current managed-runtime flow is:

```bash
tunnel-client runtimes connect \
  --alias vyrelon-local \
  --tunnel-id tunnel_... \
  --runtime-api-key env:CONTROL_PLANE_API_KEY \
  --mcp-command "multiagentos mcp serve --path /absolute/path/to/project"

tunnel-client runtimes status vyrelon-local --json
```

After the runtime is healthy, configure ChatGPT with **Connection: Tunnel** and the corresponding tunnel.

The same VYRELON MCP server is used locally and through the tunnel. Secure MCP Tunnel and `tunnel-client` are transport/connection infrastructure, not another MCP server.

### Documentation

Start here:

- [VYRELON Connection Guide](docs/VYRELON_CONNECTIONS.md) — complete connection model and developer setup.
- [Getting Started](docs/GETTING_STARTED.md) — clean-machine installation and validation.
- [Secure MCP Tunnel Setup](docs/MCP_TUNNEL.md) — OpenAI tunnel/runtime setup and troubleshooting.
- [VYRELON GitHub Connection](docs/VYRELON_GITHUB_CONNECTION.md) — local GitHub authentication and policy.
- [VYRELON MCP Architecture](docs/ARCHITECTURE_DECISIONS.md) — locked one-server architecture.

### GitHub vs VYRELON: the important boundary

Think of the connection model as two parallel paths:

```text
                  MultiAgentOS
                       |
            +----------+----------+
            |                     |
            v                     v
       GitHub path            Local path
            |                     |
 GitHub URL / repository      VYRELON runtime
            |                     |
 ChatGPT GitHub app       MCP / Secure MCP Tunnel
            |                     |
            v                     v
   Remote GitHub repo         Local project
```

**GitHub URL is not a local-project connection.** It tells the ChatGPT GitHub integration which remote repository is relevant. **VYRELON is the local execution boundary.** It is the path that can expose local filesystem access, `patch.apply`, process execution, and other explicitly permitted runtime capabilities.

### Integration boundaries

- **GitHub:** remote/durable repository state and collaboration.
- **VYRELON MCP:** local project and local tool boundary.
- **Secure MCP Tunnel:** optional private transport between OpenAI products and the local VYRELON MCP server.
- **`tunnel-client`:** tunnel-side runtime/forwarding process.
- **VYRELON:** remains independently usable without OpenAI.

The VYRELON MCP server has CI/install-smoke coverage, including a dependency-free stdio client validating initialize, tools/list, and filesystem.read. Real ChatGPT/Codex tunnel verification remains environment-specific because it requires an actual OpenAI workspace, tunnel, runtime API key, and running `tunnel-client`.

Do not expose a local MCP endpoint directly to the public internet or commit GitHub/provider/tunnel credentials.

## Installation

Install the current release from PyPI:

```bash
python -m pip install multiagentos
```

Release automation uses PyPI Trusted Publishing from GitHub Actions; no long-lived PyPI API token is required.

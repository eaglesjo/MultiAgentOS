# MultiAgentOS

MultiAgentOS is the foundation for VYRELON, a local-first, GitHub-native multi-agent development orchestrator.

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

For a clean-machine installation and the distinction between local GitHub access, ChatGPT GitHub access, Secure MCP Tunnel, and Codex integration, start with:

- [Getting Started](docs/GETTING_STARTED.md)
- [Secure MCP Tunnel Setup](docs/MCP_TUNNEL.md)
- [VYRELON GitHub Connection](docs/VYRELON_GITHUB_CONNECTION.md)

### Integration boundaries

- **Local GitHub:** VYRELON -> authenticated `gh` CLI -> GitHub.
- **ChatGPT GitHub:** ChatGPT -> GitHub app -> repositories explicitly authorized by the user.
- **ChatGPT local/private VYRELON:** ChatGPT -> Secure MCP Tunnel -> `tunnel-client` -> `multiagentos mcp serve`.
- **Codex tunnel operations:** Codex -> `tunnel-mcp` plugin -> `tunnel-client`.

The VYRELON MCP server is implemented and covered by CI. End-to-end ChatGPT connector verification still requires a real OpenAI Secure MCP Tunnel runtime and workspace configuration.

Do not expose a local MCP URL directly to the public internet or put GitHub/provider/tunnel credentials in project files.

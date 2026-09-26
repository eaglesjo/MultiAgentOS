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

## CLI

After installation:

    multiagentos detect .
    multiagentos init .
    multiagentos init . --component vyrelon
    multiagentos init . --component multi-agent
    multiagentos init . --component all
    multiagentos status .
    multiagentos github probe eaglesjo/MultiAgentOS

The initializer supports independent installation:

- `vyrelon`: VYRELON runtime, policy, lifecycle, planning/state and project profile.
- `multi-agent`: role catalog and profile-specific multi-agent definitions.
- `all`: both components.

The selected mode is recorded in:

    .multiagentos/components.json

Multi-agent installation additionally writes:

    .multiagentos/agents.json

No provider credentials or API keys are written to the project.

The read-only `status` command reports installed components, detected profiles, agent catalog entries, WorkUnits, and durable workflow checkpoints. It makes interrupted or resumable work visible without granting the CLI any additional execution authority.

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
        |
    Technology Profiles
        |
        +-- React Native
        +-- Android Native
        +-- iOS Native

## Validation

    python -m unittest discover -s tests -v

GitHub Actions runs the same test suite on pull requests and pushes.

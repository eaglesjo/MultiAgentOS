# MultiAgentOS

MultiAgentOS is the foundation for VYRELON, a local-first, GitHub-native multi-agent development orchestrator.

## Core principles

- Local-first: filesystem, shell, processes and Git are first-class.
- GitHub-native: repository, branch, commit, issue, pull request, review and CI lifecycle are first-class.
- AI/Agent agnostic: no single model, vendor, IDE or agent is required.
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
- independently installable VYRELON and multi-agent project components
- local stdlib unittest validation plus GitHub Actions CI

## Installation profiles

The Python distribution exposes explicit installation profiles:

```bash
pip install multiagentos[vyrelon]
pip install multiagentos[multi-agent]
pip install multiagentos[all]
```

These profiles are dependency-level selectors. Project-level installation is controlled separately with `multiagentos init --component ...`.

## CLI

After installation:

    multiagentos detect .
    multiagentos init . --component vyrelon
    multiagentos init . --component multi-agent
    multiagentos init . --component all
    multiagentos github probe eaglesjo/MultiAgentOS

The initializer writes profile/component metadata and, when the multi-agent component is selected, `.multiagentos/agents.json`.

No provider credentials or API keys are written to the project.

See `docs/INSTALLATION_MODES.md` for the separation between VYRELON and the optional multi-agent layer.

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


# MultiAgentOS

> **Local-first Agent Execution Runtime for multi-agent software development**

MultiAgentOS is a provider-neutral Agent Execution Runtime for orchestrating real software development work.

It separates what an AI agent decides from what the runtime is authorized to execute. Work is represented as a governed WorkUnit, routed to compatible agents and models, executed through explicit runtime boundaries, and progressed through verification, review, and handoff.

**Current release: 0.5.0**

---

## Why MultiAgentOS?

AI clients and models are good at reasoning, planning, and generating proposed changes. A production development system also needs explicit responsibility boundaries, routing, execution state, verification, recovery, and auditability.

MultiAgentOS provides that execution model.

~~~mermaid
flowchart TB
    TASK["Development Task"] --> PLAN["Plan"]
    PLAN --> DELEGATE["Delegate"]
    DELEGATE --> ASSIGN["Agent × Model Assignment"]
    ASSIGN --> EXEC["Execute"]
    EXEC --> VERIFY["Verify"]
    VERIFY --> REVIEW["Review"]
    REVIEW --> HANDOFF["Handoff"]
    HANDOFF --> DONE["Completed"]
~~~

The runtime remains provider-neutral: it does not require a specific model vendor, IDE, CLI, hosted agent platform, or coding client.

---

## 0.5.0 at a glance

Version 0.5.0 formalizes **agent orchestration and specialist runtime architecture**.

### Core execution model

The canonical development loop is:

**Understand → Plan → Delegate → Orchestrate → Execute → Verify → Review → Learn/Handoff**

Orchestration is a core architectural responsibility. Specialist agents are composed into the orchestration flow rather than creating separate execution systems.

### Agent taxonomy

MultiAgentOS distinguishes two fundamental layers:

- **Governance / Execution** — controls how work is routed, edited, executed, monitored, debugged, and reviewed.
- **Specialist** — describes the technical discipline or domain required by the work.

Specialists can be added when a real development responsibility requires them. The catalog is intentionally extensible rather than constrained to a minimal fixed set.

~~~mermaid
flowchart TB
    TASK["Task"]
    TASK --> GOV["Governance / Execution"]
    TASK --> SPEC["Specialists"]
    GOV --> PLAN["Planner"]
    GOV --> EDIT["Editor"]
    GOV --> EXEC["Executor"]
    GOV --> REVIEW["Reviewer"]
    GOV --> DEBUG["Debugger"]
    GOV --> BROWSER["Browser Agent"]
    SPEC --> RESEARCH["Research"]
    SPEC --> DEVELOPMENT["Development"]
    SPEC --> UI["UI / UX"]
    SPEC --> QUALITY["Quality"]
    SPEC --> OPS["Operations"]
~~~

### Expanded specialist disciplines

0.5.0 expands the catalog across the responsibilities needed to deliver complete software products:

| Area | Specialists |
| --- | --- |
| Architecture | software-architect |
| Backend / API / Data | backend-developer, api-developer, database-engineer |
| UX / UI | ux-designer, ui-designer, design-system-specialist, accessibility-specialist |
| Quality | qa-engineer, security-engineer, performance-engineer |
| Operations | devops-engineer |
| Platform Development | react-developer, react-native-developer, android-developer, ios-developer |
| Platform Research | React, React Native, Android, iOS development research |
| UI Research | Web/React, React Native, Android/Compose, iOS/SwiftUI research |

These roles are additive. They do not replace governance roles or introduce another orchestration layer.

---

## Orchestration

A development WorkUnit moves through explicit execution stages:

~~~mermaid
flowchart LR
    WU["WorkUnit"] --> ROUTE["Route"]
    ROUTE --> ASSIGN["Assign Agent × Model"]
    ASSIGN --> EXEC["Execute"]
    EXEC --> VERIFY["Verify"]
    VERIFY --> REVIEW["Review"]
    REVIEW --> HANDOFF["Handoff"]
    HANDOFF --> COMPLETE["Completed"]
~~~

The orchestration contract is responsible for:

1. defining the work objective;
2. resolving a compatible Agent × Model assignment;
3. preventing execution before routing succeeds;
4. invoking the execution adapter;
5. optionally verifying the result;
6. optionally reviewing the result;
7. handing off validated work;
8. moving failed work to an explicit failure state.

Orchestrator, DelegationEngine, and MultiAgentWorkflow compose these responsibilities without tying the runtime to a particular AI provider.

See [Orchestration](docs/ORCHESTRATION.md).

---

## Research before implementation

Platform-specific work can require current technical research before implementation.

~~~mermaid
flowchart LR
    TASK["Platform Task"] --> PLAN["Planner"]
    PLAN --> RESEARCH["Platform Research"]
    RESEARCH --> SPECIALIST["Platform Specialist"]
    SPECIALIST --> EDIT["Editor"]
    EDIT --> EXEC["Executor"]
    EXEC --> REVIEW["Reviewer"]
~~~

Development research focuses on current APIs, compatibility, deprecations, migration guidance, and implementation patterns.

UI research focuses on platform UI guidance, accessibility, layout, framework APIs, interaction patterns, and visual validation.

This keeps research as a specialist responsibility inside the same orchestration model.

---

## Agent × Model execution

Agent selection and model selection are separate but coordinated decisions.

~~~mermaid
flowchart TB
    WORK["WorkUnit"] --> AGENT["Agent Selection"]
    AGENT --> MODEL["Model Resolution"]
    MODEL --> ASSIGN["Agent × Model Assignment"]
    ASSIGN --> DECISION["Execution Decision"]
    DECISION --> RUNTIME["Agent Execution Runtime"]
~~~

Agents may declare capabilities, tools, permissions, supported model IDs, metadata, taxonomy, and scope awareness.

Model resolution can incorporate capability, health, and quota information while preserving provider-neutral runtime contracts.

---

## Execution governance

MultiAgentOS keeps execution authority behind an explicit runtime boundary.

~~~mermaid
flowchart TB
    INTENT["Agent Intent"] --> REQUEST["Execution Request"]
    REQUEST --> POLICY["Runtime Policy"]
    POLICY --> FS["Filesystem"]
    POLICY --> PATCH["Patch"]
    POLICY --> PROCESS["Process"]
    POLICY --> GIT["Git"]
    POLICY --> PROJECT["Project State"]
~~~

The runtime is responsible for enforcing scope, permissions, authorization, and execution state.

MCP and Tool capabilities remain **execution boundaries**. They are not separate product-architecture layers that replace orchestration.

Write and process capabilities are explicit runtime concerns and should be enabled only where the project workflow requires them.

---

## Recovery, replay, and idempotency

0.5.0 retains the runtime safety guarantees developed in the 0.4.x line.

### Durable execution state

WorkUnit state is persisted with the information required to resume execution safely, including work scope, target, environment, artifact classification, release impact, and hold state.

### Recovery identity

Recovered tool invocations preserve audit identity across recovery:

- decision_id
- agent_id
- model_id
- invocation_id
- idempotency_key

### Replay policy

Replay is classified explicitly:

| Policy | Meaning |
| --- | --- |
| **SAFE** | Automatic recovery replay is permitted |
| **REVIEW_REQUIRED** | Human approval is required before replay |
| **NEVER** | Replay is prohibited |

Replay safety is distinct from whether an operation is read-only or mutating.

### Idempotency

Tool invocations can carry stable idempotency keys. The runtime rejects reuse of an idempotency key for an existing invocation within its WorkUnit rather than silently executing the same request again.

The runtime does not claim distributed exactly-once semantics merely from the presence of an idempotency key; the receiving system must also honor the key when external side effects are involved.

---

## Local-first project execution

MultiAgentOS is designed around the real project workspace.

~~~mermaid
flowchart TB
    CLIENT["AI Client / Coding Agent"] --> RUNTIME["MultiAgentOS Agent Execution Runtime"]
    RUNTIME --> PROJECT["Local Project"]
    PROJECT --> GIT["Git"]
    GIT --> GITHUB["GitHub Repository"]
~~~

The repository provides durable source history and collaboration. The local runtime provides controlled access to the actual working tree.

These are complementary capabilities rather than interchangeable execution surfaces.

---

## Project initialization

Install the runtime:

~~~bash
python3 -m pip install "multiagentos[mcp-http]"
~~~

Initialize a project:

~~~bash
cd your-project
multiagentos init . --component all
multiagentos status .
~~~

Run a governed task:

~~~bash
multiagentos run \
  --path . \
  --objective "run tests" \
  -- python -m unittest discover -s tests -v
~~~

Start a local MCP endpoint when a client needs the runtime boundary:

~~~bash
multiagentos mcp serve-http --path .
~~~

For a project that explicitly requires write access:

~~~bash
multiagentos mcp serve-http \
  --path . \
  --allow-write
~~~

The default endpoint is:

~~~text
http://127.0.0.1:8000/mcp
~~~

Project configuration is stored under:

~~~text
.multiagentos/
├── components.json
├── execution.json
├── chat.json
├── agents.json
└── state/
~~~

Credentials and provider API keys are not persisted in project configuration.

---

## Project-scoped runtime services

Multiple projects can be managed independently.

~~~bash
multiagentos mcp install \
  --path /absolute/path/to/project1 \
  --port 8000 \
  --allow-write

multiagentos mcp install \
  --path /absolute/path/to/project2 \
  --port 8001 \
  --allow-write
~~~

Inspect or remove a managed service:

~~~bash
multiagentos mcp status --path /absolute/path/to/project1
multiagentos mcp uninstall --path /absolute/path/to/project1
~~~

The repository supports OS-native lifecycle management, including per-user services on macOS and Windows.

---

## Verification and release gate

Version 0.5.0 was released only after the release candidate passed the repository's release validation.

The release gate covered:

- the full contract test suite;
- installation smoke validation;
- MCP Streamable HTTP inspection;
- package build and artifact validation;
- native package matrix validation for Windows x64, Ubuntu amd64, macOS Intel x64, and macOS ARM64;
- specialist catalog contract coverage;
- recovery, replay-policy, tool identity, and idempotency regression coverage.

The 0.5.0 tag is the formal release marker for this version.

For the current verification command:

~~~bash
python -m unittest discover -s tests -v
~~~

GitHub Actions remains the authoritative CI execution environment for repository-wide release validation.

---

## Documentation

### Architecture

- [Orchestration](docs/ORCHESTRATION.md)
- [Agent Taxonomy and Routing](docs/AGENT_TAXONOMY.md)
- [Agent Catalog](docs/AGENT_CATALOG.md)
- [Architecture Decisions](docs/ARCHITECTURE_DECISIONS.md)

### Runtime and project setup

- [Getting Started](docs/GETTING_STARTED.md)
- [Project Installation](docs/PROJECT_INSTALLATION.md)
- [Agent Execution Runtime Connection Guide](docs/AGENT_EXECUTION_RUNTIME_CONNECTIONS.md)
- [Agent Execution Runtime GitHub Connection](docs/AGENT_EXECUTION_RUNTIME_GITHUB_CONNECTION.md)
- [Bounded GitHub Actions Execution Missions](docs/GITHUB_ACTIONS_EXECUTION_MISSIONS.md)

### Optional connectivity and platform integration

- [Secure MCP Tunnel Setup](docs/MCP_TUNNEL.md)
- [macOS MCP Service](docs/MACOS_MCP_SERVICE.md)
- [macOS Tunnel Service](docs/MACOS_TUNNEL_SERVICE.md)
- [ChatGPT Client Capability Matrix](docs/CHATGPT_CLIENT_CAPABILITIES.md)

MCP, Tool, and remote connectivity documentation describes existing execution boundaries and integrations. It does not define additional product-architecture layers.

The English README is the canonical technical overview.

**[한국어 README](README.ko.md)**

---

## Release history

See [CHANGELOG.md](CHANGELOG.md) for the complete release history.

## License

See [LICENSE](LICENSE).

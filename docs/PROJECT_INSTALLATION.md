# Project Installation

MultiAgentOS is installed **into a project workspace**, not into an IDE.

The IDE and coding agent remain client/workspace layers. MultiAgentOS provides the project-scoped execution and governance boundary.

## Installation flow

```mermaid
flowchart LR
    INSTALL["pip install multiagentos"] --> INIT["multiagentos init ."]
    INIT --> DETECT["Project profile detection"]
    DETECT --> BOOT["Project runtime bootstrap"]
    BOOT --> CONFIG[".multiagentos configuration"]
    BOOT --> AGENTS["AGENTS.md"]
    BOOT --> MCP["Project MCP contract"]
    CONFIG --> RUN["multiagentos run / chat"]
    MCP --> CLIENT["MCP-capable coding agent"]
    CLIENT --> RUNTIME["Agent Execution Runtime"]
    RUN --> RUNTIME
    RUNTIME --> PROJECT["Real project workspace"]
```

## What multiagentos init creates

```mermaid
flowchart TB
    INIT["multiagentos init ."]
    INIT --> PROFILE[".multiagentos/profile.json"]
    INIT --> COMPONENTS[".multiagentos/components.json"]
    INIT --> EXEC[".multiagentos/execution.json"]
    INIT --> CHAT[".multiagentos/chat.json"]
    INIT --> AGENTS_JSON[".multiagentos/agents.json"]
    INIT --> MCP[".multiagentos/mcp.json"]
    INIT --> STATE[".multiagentos/state/"]
    INIT --> CHECKPOINTS[".multiagentos/checkpoints/"]
    INIT --> SESSIONS[".multiagentos/sessions/"]
    INIT --> INSTRUCTIONS["AGENTS.md"]
    PROFILE --> ROUTING["Profile-aware routing"]
    AGENTS_JSON --> ROUTING
    MCP --> CONNECTION["Local MCP connection contract"]
    EXEC --> EXECUTION["Execution configuration"]
    CHAT --> CHAT_RUNTIME["Chat Agent configuration"]
```

Existing AGENTS.md, .multiagentos/mcp.json, and .multiagentos/.gitignore files are preserved on re-initialization.

Runtime state is kept under .multiagentos/state/, .multiagentos/checkpoints/, and .multiagentos/sessions/ and is ignored by the generated runtime-local .gitignore.

## Initialize

From the project root:

```bash
python3 -m pip install "multiagentos[mcp-http]"
multiagentos init .
multiagentos status .
```

The initializer detects the project profile and creates the project-local runtime contract. It does not install an IDE extension, modify IDE settings, start a background service, or require a paid AI API key.

## Runtime connection

```mermaid
flowchart TB
    IDE["IDE / Workspace"]
    AGENT["Coding Agent"]
    MCP_CONFIG[".multiagentos/mcp.json"]
    MCP["127.0.0.1:8000/mcp"]
    RUNTIME["MultiAgentOS Agent Execution Runtime"]
    PROJECT["Project"]
    IDE --> AGENT
    AGENT --> MCP_CONFIG
    MCP_CONFIG --> MCP
    MCP --> RUNTIME
    RUNTIME --> PROJECT
```

The generated MCP contract is client-neutral. Client-specific configuration remains the responsibility of the client and is never generated as an IDE plugin.

Default endpoint:

```text
http://127.0.0.1:8000/mcp
```

The generated configuration starts with read-only capabilities:

- allow_write: false
- allow_process: false

Enable side-effecting capabilities only through an explicit MCP server/service command:

```bash
multiagentos mcp serve-http \
  --path . \
  --allow-write \
  --allow-process
```

## Project lifecycle

```mermaid
flowchart LR
    INIT["Initialized"] --> DETECT["Profile detected"]
    DETECT --> CONFIGURED["Runtime configured"]
    CONFIGURED --> CONNECTED["MCP connected"]
    CONNECTED --> EXECUTING["Agent execution"]
    EXECUTING --> VERIFY["Verification"]
    VERIFY --> DONE["Project task complete"]
```

The project configuration is durable repository-local metadata. Execution state is local runtime state and must not contain credentials.

## Governance boundary

```mermaid
flowchart TB
    REQUEST["Agent request"]
    REQUEST --> PROFILE["Project profile"]
    REQUEST --> SCOPE["Work Unit scope"]
    REQUEST --> POLICY["Runtime policy"]
    PROFILE --> ROUTER["Agent routing"]
    SCOPE --> ROUTER
    POLICY --> ROUTER
    ROUTER --> EXEC["Execution"]
    EXEC --> EVIDENCE["Evidence / verification"]
    EVIDENCE --> APPROVAL["Human approval when required"]
```

MultiAgentOS remains the execution and governance authority. A coding agent may reason about the task, but it does not bypass the project runtime boundary.

## Recommended next step

After initialization, connect the project's MCP endpoint to the coding agent and run a **read-only inspection first**. Then enable write/process capabilities when the work unit requires them.

See Getting Started, Agent Taxonomy, and Agent Execution Runtime Connection Guide.

# VYRELON installation modes

MultiAgentOS separates the **VYRELON runtime** from the **multi-agent layer** at installation time.

## Components

### VYRELON only

Use when a project needs the local/Git/GitHub execution runtime without installing the built-in specialist catalog.

```bash
multiagentos init . --component vyrelon
```

This installs:

- project profile detection
- local filesystem/process/Git runtime
- policy-controlled GitHub runtime
- planning/state infrastructure
- VYRELON runtime facade

It does not materialize `.multiagentos/agents.json`.

### Multi-agent only

Use when the project wants the agent catalog layer separately.

```bash
multiagentos init . --component multi-agent
```

This materializes the multi-agent catalog independently. The catalog is intentionally defined in terms of the VYRELON contracts, so it can be enabled without changing the VYRELON core.

### Both

```bash
multiagentos init . --component all
```

This installs the VYRELON runtime and the multi-agent layer together.

## Important separation

The multi-agent layer is an extension of VYRELON, not a replacement for it.

- **VYRELON** owns execution, Git, GitHub, policy, lifecycle, planning, state and routing.
- **Multi-agent** owns role catalogs, specialist agents, delegation targets and review participants.
- A model provider is neither VYRELON nor a required part of the multi-agent layer.

This means a project can run VYRELON as the execution/control runtime and add or remove multi-agent capabilities independently.

## ChatGPT Free operating model

VYRELON does not require an OpenAI API key. It is deliberately provider-neutral.

A ChatGPT Free conversation can be the human-facing planning/control surface when the user supplies the resulting instructions to the local VYRELON CLI. GitHub can also be connected to ChatGPT where the user's ChatGPT experience and plan expose that app.

However, standard ChatGPT GitHub access is currently read/search oriented; OpenAI documents that direct GitHub writes are done through Codex, and local MCP servers are not directly reachable from ordinary ChatGPT. Therefore this project must not pretend that a free ChatGPT chat is itself a local shell or a GitHub write API.

The VYRELON design keeps those concerns separate:

```text
ChatGPT Free (conversation / reasoning)
        |
        | user-directed task
        v
VYRELON local runtime
        |
        +--> Local filesystem / shell / Git
        |
        +--> GitHub runtime
        |
        +--> optional multi-agent layer
```

This keeps the VYRELON runtime usable with ChatGPT Free without coupling the product to a paid API.

## Future adapter boundary

A future ChatGPT/Codex/MCP bridge may automate the handoff between the conversation and VYRELON. Such a bridge must be an adapter; it must not move local/GitHub execution responsibilities into the model layer.

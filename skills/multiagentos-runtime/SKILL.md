---
name: multiagentos-runtime
description: Use MultiAgentOS for local project execution, persistent WorkUnits, inspection, and conservative recovery.
---

# MultiAgentOS Runtime

Use the installed `multiagentos` CLI when local execution authority is required.

- Inspect project state before changing files.
- Use persistent WorkUnits for substantial tasks.
- Inspect runtime events before attempting recovery.
- Never replay a tool call that has no durable tool result without explicit human review.
- Treat filesystem writes, process execution, patch application, Git operations, and MCP calls as side effects.

Common commands:

```bash
multiagentos status .
multiagentos run --path . --objective "..."
multiagentos resume <work-unit-id> --path .
multiagentos mcp serve --path .
```

If resume requires human review, stop and present the pending tool call IDs and reason instead of retrying the side effect.

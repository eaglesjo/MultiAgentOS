# VYRELON Orchestration

VYRELON has an executable, provider-neutral lifecycle:

1. WorkUnit describes the objective.
2. DelegationEngine resolves a compatible agent/model assignment.
3. WorkUnit enters execution only after routing succeeds.
4. Orchestrator invokes an injected AgentExecutor.
5. When a verifier is supplied, the WorkUnit enters verification before completion.
6. Verification failure or execution failure moves the WorkUnit to failed.
7. Successful work reaches completed.

The executor and verifier are protocols. VYRELON therefore does not require a specific AI vendor, CLI, IDE, MCP server, or hosted agent platform.

The next integration layers can implement executors for local processes, CLI agents, API agents, IDE agents, MCP-backed agents, or remote/containerized agents.

## Work state safety

WorkUnit transitions are explicit and validated. Terminal states cannot silently move back into execution, and routing failures leave a work unit in its original state rather than falsely marking it as executing.

## Local validation

```bash
python -m unittest discover -s tests -v
```

GitHub Actions is now available as a supplementary CI layer because MultiAgentOS is public. Local validation remains useful for fast development feedback.

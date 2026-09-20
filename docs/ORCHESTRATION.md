# VYRELON Orchestration

VYRELON now has an executable core loop:

1. WorkUnit describes the objective.
2. DelegationEngine assigns the work to an Agent.
3. AIRouter selects a compatible model from the AI pool.
4. Orchestrator invokes a vendor-neutral executor.
5. Successful execution transitions the WorkUnit to completed.
6. Execution errors transition it to failed and propagate the error.

The executor is injected. VYRELON therefore does not require a specific AI vendor,
CLI, IDE, MCP server, or hosted agent platform.

The next integration layer can implement executors for local processes, CLI agents,
API agents, IDE agents, MCP-backed agents, or remote/containerized agents without
changing this orchestration contract.

## Local validation

python -m unittest discover -s tests -v

# VYRELON Orchestration

VYRELON now models the full executable development loop:

1. WorkUnit describes the objective.
2. DelegationEngine resolves a compatible agent/model assignment.
3. WorkUnit enters execution only after routing succeeds.
4. Orchestrator invokes an injected AgentExecutor.
5. Verification is optional and moves the WorkUnit into VERIFYING.
6. Review is optional and moves the WorkUnit into REVIEWING.
7. Successful validated/reviewed work passes through HANDOFF and reaches COMPLETED.
8. Execution, verification, or review failures move the WorkUnit to FAILED.

This preserves the intended flow:

Understand -> Plan -> Delegate -> Orchestrate -> Execute -> Verify -> Review -> Learn/Handoff

The executor, verifier, and reviewer are protocols. VYRELON therefore does not require a specific AI vendor, CLI, IDE, MCP server, or hosted agent platform.

## State safety

WorkUnit transitions are explicit and validated. Terminal states cannot silently move back into execution, and routing failures leave a work unit in its original state rather than falsely marking it as executing.

## Extension points

The next layers can persist handoff artifacts, review feedback, agent memory, and learned routing signals without changing the core orchestration contract.

## Local validation

python -m unittest discover -s tests -v

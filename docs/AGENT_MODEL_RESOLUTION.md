# Agent x Model Resolution

AgentModelResolver is the canonical boundary between Agent selection and model execution.

1. Agent capability eligibility is established by AgentSelector.
2. Agent.model_ids is an allowlist when declared.
3. Model capability compatibility is evaluated by the existing CapabilityRegistry.
4. Health and quota constraints are evaluated by AIRouter.
5. The resolver returns the assignment and complete routing explanation.

Agent identity/capability and Model capability remain separate while producing one auditable executable assignment.

# Agent Capability Registry

AgentCapabilityRegistry is the first-class capability index for Agent selection.

- AgentContract remains the canonical identity, taxonomy, permissions, and execution contract.
- AgentCapabilityRegistry indexes declared capabilities, tools, permissions, and model preferences.
- CapabilityRegistry indexes model capabilities and runtime observations.
- AgentSelector can keep deterministic taxonomy routing while using capability matching as an additional bounded eligibility signal.

Intended resolution:

    WorkUnit requirements
           ↓
    AgentCapabilityRegistry
           ↓
    compatible Agent candidate pool
           ↓
    AgentSelector
           ↓
    Model Capability Registry
           ↓
    Agent × Model resolution

The registry does not introduce vendor-specific model logic or bypass governance validation.

# VYRELON Agent-to-Model Bridge

The ModelBackedAgentExecutor connects the orchestration layer to the model runtime.

Flow:

WorkUnit -> AgentContract -> AIRouter -> ModelSpec -> ModelAdapter -> ModelResponse

This is the point where VYRELON becomes an actual model-driven agent runtime rather than only a planning or assignment framework.

The bridge is provider-neutral. A model can be backed by a CLI, HTTP API, MCP gateway, local inference server, IDE bridge, or another adapter without changing AgentContract or Orchestrator.

The agent receives role and capability context, while the WorkUnit objective and inputs become the model request. Permissions remain orchestration/runtime policy concerns and are not inferred from model output.

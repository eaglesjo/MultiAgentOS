# VYRELON Agent Runtime

The runtime layer is deliberately separate from orchestration and model selection.

- ExecutionRequest carries the selected Agent, model ID, and WorkUnit.
- RuntimeExecutor defines the adapter boundary.
- ExecutionPolicy controls process, filesystem, Git, network, and GitHub write capabilities.
- LocalProcessExecutor provides a concrete local executor using an explicit argv list.

## Why argv instead of shell text

The first local executor accepts list[str] / tuple[str, ...] commands and invokes subprocess.run without a shell. This keeps command construction explicit and avoids silently turning a model-produced string into a shell program.

## Approval boundary

Read/analyze/test operations can be permitted automatically. Git write, GitHub write, PR creation, push, and merge remain explicit policy boundaries. The policy object is an enforcement primitive; higher-level approval workflows will be added by VYRELON's orchestration layer.

## Extension points

The same RuntimeExecutor boundary can host:

- CLI agents
- API agents
- IDE agents
- MCP-backed agents
- remote agents
- containerized agents
- local model agents

No model provider is required by the runtime contract.

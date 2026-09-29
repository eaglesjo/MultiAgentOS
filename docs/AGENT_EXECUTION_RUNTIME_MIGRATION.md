# Agent Execution Runtime API Migration

## Migration status

The Agent Execution Runtime migration is complete.

The canonical supported Python surfaces are:

- `runtime.AgentExecutionRuntime`
- `runtime.agent_execution_runtime.AgentExecutionRuntime`
- `core.contracts.agent_execution_runtime`
- `runtime.mcp.agent_execution_runtime_server.AgentExecutionRuntimeMCPServer`

## Migration rule

New and existing MultiAgentOS code uses the Agent Execution Runtime names directly.

The former legacy runtime naming has been fully removed from the repository:

- no legacy runtime compatibility module;
- no legacy runtime class alias;
- no legacy MCP server alias;
- no legacy configuration namespace;
- no legacy documentation filenames;
- no legacy IDE integration identifiers.

Because MultiAgentOS has no external consumers requiring the retired API surface, this was completed as a breaking internal migration rather than a compatibility-preserving release.

## Runtime and tunnel naming

The local managed tunnel runtime uses the canonical alias:

`agent-execution-runtime-local`

The Secure MCP Tunnel itself remains infrastructure. Its opaque `tunnel_id` is independent of the runtime's human-readable alias.

## Validation

The repository includes a regression invariant that scans source and documentation and fails if the retired runtime name reappears.

The Agent Execution Runtime Foundation workflow validates:

1. the complete Python test suite;
2. package installation and CLI bootstrap;
3. the cost-free acceptance path;
4. release artifact creation and validation.

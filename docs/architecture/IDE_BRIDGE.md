# Agent Execution Runtime IDE Loopback Bridge

The IDE adapters for Xcode, VS Code, and Android Studio communicate with Agent Execution Runtime through a local HTTP bridge.

## Security boundary

- Default bind address is `127.0.0.1`.
- Remote binding is rejected unless explicitly enabled by policy.
- Requests require a bearer token.
- Request bodies are size-limited.
- IDE events, explicit agent work requests, and Agent Execution Runtime commands use separate endpoints.
- The bridge does not grant filesystem, shell, Git, MCP, or network permissions by itself. Those remain Agent Execution Runtime runtime permissions.

Endpoints:
- `POST /v1/ide/event`
- `POST /v1/ide/work`
- `POST /v1/ide/command`

The bridge is a transport boundary, not a second execution runtime.

## Runtime integration

An application embedding Agent Execution Runtime can construct `IDEBridge` with event and command handlers, then run `IDEBridgeServer` on the loopback interface.

The token should be generated and stored by the local Agent Execution Runtime installation rather than hard-coded into an IDE extension.

## Agent work path

`POST /v1/ide/work` is the explicit execution boundary for an IDE action that asks Agent Execution Runtime to do work. Agent Execution Runtime resolves the project-scoped agent, creates a persistent `WorkUnit`, executes it through the existing Agent/Model lifecycle, and returns the result to the IDE as a normalized command. Passive IDE events never start agent execution.

# Agent Execution Runtime VS Code Adapter

A thin VS Code extension that translates VS Code editor/workspace state into the provider-neutral Agent Execution Runtime IDE contract.

## Boundary

`VS Code Extension API → IDEContext / IDECommand → local Agent Execution Runtime bridge`

The extension does not implement filesystem, shell, Git, MCP, model, or multi-agent execution itself.

## Local bridge

Default endpoint:

`http://127.0.0.1:8787`

Expected endpoints:

- `POST /v1/ide/context`
- `POST /v1/ide/command`

Optional bearer authentication is configured through `agentExecutionRuntime.token`.

The bridge is intentionally loopback-oriented. Do not expose this endpoint publicly.

## Build

From this directory:

```bash
npm install
npm run check
npm run compile
```

The adapter remains optional; Agent Execution Runtime core does not require Node.js or VS Code.

# Agent x Model x Tool Authorization

`ToolAuthorizationPolicy` extends the execution authorization boundary to MCP tools without introducing a second permission system.

The existing `MCPTool.permissions` and `MCPToolProfile.allows()` remain authoritative for tool-level access. `ExecutionDecision` adds the execution-level binding: the tool invocation must belong to the exact authorized Agent and therefore inherits the exact selected Model and decision ID.

```text
ExecutionDecision
      |
      +-- Agent identity
      +-- Model identity
      +-- governance authorization
      |
      v
ToolAuthorizationPolicy
      |
      +-- MCPTool permissions
      +-- MCPToolProfile policy
      +-- side-effect policy
      |
      v
Authorized Tool Invocation
```

A denied execution decision cannot authorize a tool call. An Agent mismatch is denied, and existing MCP profile/permission rules remain enforced.

This creates an auditable chain:

`WorkUnit -> AgentPlan -> Agent x Model ExecutionDecision -> ToolAuthorization -> ToolInvocation`


## Runtime enforcement

The authorization contract is enforced at the real external MCP invocation boundary in
`MCPToolProxy.call(..., decision=...)`.

When an `ExecutionDecision` is supplied:

1. the exact Agent must be supplied;
2. the proxy resolves the concrete `MCPTool` from the connected server;
3. `ToolAuthorizationPolicy` validates the decision, Agent, MCP permissions, and optional profile;
4. an unauthorized result raises before `MCPClient.call_tool()` is reached;
5. an authorized call receives `tool_authorization` metadata containing the exact
   `decision_id`, Agent, Model, and tool identity.

Therefore a retry that creates a new `ExecutionDecision` cannot silently reuse the
authorization of the previous attempt.


## Durable audit trace

When an Agent × Model execution supplies its `ExecutionDecision` to the tool-calling runtime, the exact
`decision_id`, Agent ID, and Model ID are copied into each durable `ToolInvocationRecord` and into
the corresponding `TOOL_CALL` / `TOOL_RESULT` runtime-event payloads.

The observability layer exposes the same identity chain as `tool_decision_timeline`. This makes a
tool invocation independently traceable back to the authorization decision that permitted that
execution attempt.

Direct standalone MCP service calls that do not originate from an authorized Agent execution do not
invent a decision ID; they remain explicitly outside the Agent × Model authorization chain.

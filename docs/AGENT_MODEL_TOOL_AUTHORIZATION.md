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

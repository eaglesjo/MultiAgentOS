# Agent Execution Runtime MCP Cost Boundary

Agent Execution Runtime treats MCP as a local execution/integration boundary, not a paid MCP service dependency.

## Default

Built-in/local MCP providers are the default path:

- run on the developer's machine or controlled project environment
- no MCP-service subscription is required
- transport can be stdio or local Streamable HTTP
- model/provider costs remain separate from MCP costs

Mobile MCP is consumed as a locally executed MCP provider. MultiAgentOS does not proxy it through a paid SaaS MCP service.

## External MCP

External MCP servers are optional extensions.

- source "external" defaults to enabled false
- external configuration should explicitly opt in with enabled true
- requires_explicit_enable can make the intent explicit
- cost_policy "external_service_possible" documents that the external service may charge
- agent/tool permissions and MCP profiles still apply

## Design rule

No core Agent Execution Runtime workflow may require a paid external MCP service to function.

External MCP is an integration option, not a platform dependency.

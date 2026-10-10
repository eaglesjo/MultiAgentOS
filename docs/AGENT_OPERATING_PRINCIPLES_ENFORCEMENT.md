# Agent Operating Principles Enforcement Map

This document separates controls that are technically enforced today from workflow expectations that still depend on the acting agent or human reviewer. A documented principle is not automatically a runtime guarantee.

## Control matrix

| Principle | Existing control | Enforcement level | Remaining gap |
|---|---|---|---|
| Execute directly when authorized and capable | `AGENTS.md` workflow requirement | Procedural | No generic runtime can force an assistant to use every available external connector or complete every user task. Tool availability and authorization vary by environment. |
| Verify actual state after meaningful actions | Required CI checks, source-SHA verification and `validation-evidence.json` in `.github/workflows/ci.yml`; repository tests | Partial technical + procedural | CI verifies the code under test, not every external mutation performed by every agent. Each connector action still needs a read-after-write check. |
| Be explicit about capability and permission limits | `runtime/tool_calling.py` checks granted permissions, capabilities and approvals; MCP execution authorization is checked at `runtime/mcp/proxy.py` | Technical for covered tool boundaries; procedural elsewhere | Integrations that bypass these runtime boundaries must be reviewed and tested individually. |
| Include cleanup in the plan | `AGENTS.md` and the minimum completion checklist | Procedural | There is no universal cleanup registry covering remote branches, PRs, cloud resources and arbitrary external side effects. Cleanup support depends on each connector. |
| Report evidence, not assumptions | Required CI checks and validation evidence artifact; durable tool ledger and runtime events | Partial technical | Evidence can be incomplete when an integration does not expose read-back, audit or status APIs. A successful API response alone is not proof of final state. |
| Respect authorization and safety boundaries | Required status checks and protected `main`; runtime permission, capability and approval gates; MCP Agent × Model execution-decision authorization | Technical for configured repository/runtime paths | Protection and policy coverage must be verified for each repository and adapter. No control should be bypassed to satisfy direct-execution preference. |
| Plan for completion | Required completion checklist in `docs/AGENT_OPERATING_PRINCIPLES.md`; CI checks the policy contract | Procedural + policy-document regression check | CI can detect removal of required policy text, but cannot prove that a future agent actually followed the plan. |

## Existing runtime gates to preserve

- `runtime/tool_calling.py`: checks registered tool identity, granted permissions, capability policy, and required approval before invoking a registered handler.
- `runtime/mcp/proxy.py` and `core/contracts/tool_authorization.py`: bind MCP access to the authorized execution decision, Agent identity, tool permissions, and optional MCP profile.
- `core/tool_ledger.py` and the runtime event store: preserve invocation state and decision identity for supported execution paths.
- `.github/workflows/ci.yml`: verifies a full source SHA, checks out that exact SHA, runs the policy contract and tests, and uploads validation evidence.
- The `main` ruleset: requires status checks and protects the default branch; branch protection must not be bypassed to make a task appear complete.

## Recommended enforcement sequence

1. **Keep the CI contract check** as a lightweight guard against accidental policy drift. It is not a behavioral compliance test.
2. **Add negative tests at each side-effect boundary**: missing permission, disabled capability, absent/invalid approval, mismatched execution identity, and failed read-back must not be reported as success.
3. **Require read-after-write evidence in repository adapters** for branch, pull request, file, and workflow mutations where the API supports read-back.
4. **Make cleanup outcomes explicit** in operation results: completed and verified, not needed, blocked by missing capability, or still pending. Never emulate deletion with a different destructive operation.
5. **Keep connector-specific limits visible**. If an API does not support a required action, report the exact blocked operation and preserve all other completed work.
6. **Do not overstate coverage**: a passing test suite only validates the tested paths. Extend coverage when new adapters or side-effecting tools are added.

## Acceptance criteria for future runtime work

- Unauthorized or unapproved side effects are rejected before the external handler/client is called.
- The rejection is observable and auditable without leaking secrets.
- Successful mutations are read back where supported, and the resulting identity/state is recorded.
- Cleanup failures remain explicit and do not get relabeled as success.
- Tests cover both allowed and denied paths for every new side-effect boundary.

This map is a review guide, not a substitute for the implementation and test evidence of each control.

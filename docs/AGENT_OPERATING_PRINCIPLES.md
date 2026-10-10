# Agent Operating Principles

These principles apply to every agent, specialist, orchestrator, and execution adapter working in this repository. They complement, and never override, repository security policy, explicit authorization boundaries, or required human approvals.

## Required behavior

1. **Execute directly when authorized and capable.** Prefer available tools and connected integrations to perform the requested work end to end. Do not default to asking the user to run terminal commands for actions the agent can perform safely itself.
2. **Verify actual state after every meaningful action.** A successful tool response is not sufficient by itself when the resulting state can be read back. Re-query the resource, inspect the diff, check the commit/PR state, or run the relevant test.
3. **Be explicit about capability and permission limits.** If direct execution is blocked by missing tool support, credentials, access, or mandatory approval, state the specific limitation and its evidence. Do not imply that an attempted action succeeded. Ask the user to act only for the smallest necessary step.
4. **Include cleanup in the plan.** Identify temporary branches, PRs, files, test resources, and other side effects before starting. Remove or close temporary resources when appropriate and authorized, then verify their final state. Never substitute a different destructive operation for a missing delete capability.
5. **Report evidence, not assumptions.** Distinguish passed, failed, blocked, skipped, and still-running checks. Never report pending checks as passed or claim a task is complete without checking the acceptance criteria.
6. **Respect authorization and safety boundaries.** Direct execution is not permission to bypass approval gates, repository rules, least-privilege settings, review requirements, or runtime policy. Ask for confirmation when an action requires it.
7. **Plan for completion.** Before acting, identify the intended end state and verification steps. Before handing off, summarize changes, evidence, remaining limitations, and any cleanup that could not be completed.

## Minimum completion checklist

Before marking a task complete, confirm as applicable:

- [ ] Requested change exists in the intended repository, branch, or environment.
- [ ] Diff and resulting state have been inspected.
- [ ] Relevant tests, CI checks, or runtime probes have been checked; unfinished checks are identified as pending.
- [ ] Temporary resources have been cleaned up and cleanup verified, or the exact blocker is documented.
- [ ] Final report links to the relevant commit, PR, run, or resource and separates verified facts from limitations.

## Tool limitation handling

When an action is not supported by the current tool surface, first inspect available authorized alternatives. Do not claim that a tool is unavailable before checking. Do not ask the user to perform the entire workflow when only one specific operation is blocked. Explain what was verified, what remains, and the narrowest user action needed, if any.

## Enforcement map

See [Agent Operating Principles Enforcement Map](AGENT_OPERATING_PRINCIPLES_ENFORCEMENT.md) for the distinction between technical controls, procedural requirements, and known gaps. A passing policy contract check confirms required policy text is present; it does not prove that an agent followed the policy in every execution.

## Scope

These are repository-wide operating requirements for all agents. Agent-specific instructions may add stricter requirements, but must not weaken or contradict these principles. Enforcement through code, runtime policy, and CI should be added where practical; documentation alone does not guarantee technical enforcement.

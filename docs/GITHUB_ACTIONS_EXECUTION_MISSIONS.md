# Bounded GitHub Actions Execution Missions

MultiAgentOS remains local-first. GitHub Actions is an execution provider for bounded remote work, not an interactive development shell.

## Mission contract

Every mission fixes:
- repository identity;
- exact 40-character source commit SHA;
- one maintained workflow;
- one bounded operation (`test`, `package`, or `verify`);
- explicit inputs;
- minimum workflow permissions;
- expected evidence and terminal state.

The runtime dispatches the workflow, polls the resulting run, collects artifact metadata, and verifies the returned evidence before treating the mission as successful.

## Execution path

```text
WorkUnit
   |
   v
Execution Mission
   |
   +-- repository
   +-- source SHA
   +-- operation
   +-- inputs
   +-- expected outputs
   |
   v
GitHub Actions
   |
   +-- checkout exact SHA
   +-- verify HEAD == source SHA
   +-- execute bounded operation
   +-- publish short-lived evidence artifact
   |
   v
Execution Evidence
   |
   v
Verification
   |
   +-- source identity
   +-- terminal status
   +-- success conclusion
   +-- expected artifacts
```

## Policy

`github.actions` is disabled by default. Enable it explicitly through `ExecutionPolicy`:

```python
ExecutionPolicy(allow_github_actions=True)
```

GitHub write permission and GitHub Actions execution permission are separate capabilities.

## Failure handling

A failed mission is not automatically retried. Inspect the run, failed job/step, logs, artifacts, and source identity first. Only a failure supported as transient should be retried. Source changes are not a valid response to an infrastructure failure without additional evidence.

## Security boundary

The maintained mission workflow has `contents: read`, checks out an immutable SHA, accepts only a bounded operation choice, does not expose secrets, and keeps artifact retention at seven days.

Do not add arbitrary shell commands as workflow inputs. If a new operation is needed, add it as reviewed workflow code and a typed mission operation.

GitHub Actions policies can also restrict who may trigger `workflow_dispatch`; repository/organization policy remains authoritative.

## Relationship to the local runtime

The normal path is:

```text
Agent -> WorkUnit -> local Agent Execution Runtime
```

Remote execution is:

```text
Agent -> WorkUnit -> Execution Mission -> GitHub Actions
```

The remote path is selected only when it is actually needed. It does not replace the local runtime, MCP boundary, or existing GitHub repository integration.

## Provenance

This design incorporates the bounded-mission, exact-source, evidence-verification, diagnose-before-retry, and bounded-cleanup principles researched from the public `luna-chat-coder` repository. The implementation is native to MultiAgentOS and contains no dependency on that repository or its naming.

GitHub's current Actions guidance also supports explicit workflow inputs, least-privilege `GITHUB_TOKEN` permissions, immutable action references, and careful control over who may trigger manual workflows.

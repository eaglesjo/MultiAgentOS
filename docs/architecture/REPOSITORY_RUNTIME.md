# Agent Execution Runtime Repository Runtime

Repository Runtime is the durable repository boundary between local execution, GitHub, validation, and WorkUnit continuity.

## Responsibilities

- Git status and diff through the existing Git Runtime
- GitHub workflow evidence through the existing GitHub gateway
- checkpoint creation without destructive reset operations
- recovery through policy-controlled Git stash restoration
- repository evidence persisted under `.multiagentos/evidence`
- checkpoint metadata persisted under `.multiagentos/checkpoints`

## Checkpoint model

A checkpoint records a durable Agent Execution Runtime checkpoint identifier and captures the working tree through Git stash when local changes exist. Clean repositories are also checkpointable; those checkpoints are marked as requiring no stash recovery.

Recovery never performs an implicit `git reset --hard`. It restores only a Agent Execution Runtime-created checkpoint stash, and Git write policy remains enforced.

## Evidence model

Repository evidence combines Git status/diff, the latest checkpoint identifier, optional Validation Runtime evidence, and optional GitHub workflow state.

This allows a WorkUnit to carry evidence across local execution and CI without coupling the core runtime to a particular CI vendor.

## Cost and provider boundary

GitHub is an explicit repository integration, not an MCP billing dependency. Validation remains local/provider-neutral. External MCP remains optional and disabled by default.

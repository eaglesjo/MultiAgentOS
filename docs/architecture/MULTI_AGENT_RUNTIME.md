# Multi-Agent Runtime

Multi-Agent Runtime is the orchestration layer above the existing Agent Execution Runtime runtimes.

## Stage model

```text
WorkUnit
   |
   v
Planner
   |
   v
Dependency-ordered Plan
   |
   +--> Agent A / Session / Tools
   |
   +--> Agent B / Session / Tools
   |
   +--> Agent C / Session / Tools
             |
             v
          Handoff
             |
             v
          Complete
```

Each plan step has an explicit agent and dependency list. Every stage is executed as a child WorkUnit while the parent WorkUnit remains the durable coordination boundary.

## Runtime composition

A stage can use the existing:

- AI Runtime for provider/model execution
- Local Tool Runtime for filesystem, shell, Git, and patch
- MCP Runtime for controlled tools
- Repository Runtime for checkpoints, GitHub, CI, recovery, and evidence
- Validation Runtime for tests and validation evidence

No Harness abstraction is introduced.

## Handoff

After each completed stage, Agent Execution Runtime records a handoff artifact identifying the previous and next agents. Stage outputs are recorded in the parent WorkUnit metadata.

## Failure and recovery

A failed stage fails the parent WorkUnit and persists the failure through the existing WorkStateStore. Repository checkpoints can be used before orchestration so recovery can restore the working tree without destructive reset operations.

## Cost boundary

Multi-Agent Runtime does not require an external MCP service. Agents use the existing built-in/local MCP path by default, with external MCP remaining an explicit opt-in.

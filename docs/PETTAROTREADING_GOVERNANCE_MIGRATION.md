# PetTarotReading Governance Migration

MultiAgentOS absorbs the strongest governance patterns from PetTarotReading without copying its Agent OS runtime.

## Target architecture

```mermaid
flowchart TB
    PTR["PetTarotReading governance patterns"]
    PTR --> SCOPE["Scope Lock"]
    PTR --> ROLES["Execution roles"]
    PTR --> ART["Artifact contracts"]
    PTR --> EVID["Evidence discipline"]
    PTR --> APPROVAL["Human approval"]
    PTR --> HOLD["HOLD safety"]
    PTR --> VALIDATE["Deterministic validation"]

    MAOS["MultiAgentOS native runtime"]
    SCOPE --> CONTRACTS["Core contracts"]
    ROLES --> AGENTS["Agent catalog / registry"]
    ART --> HANDOFF["Artifacts / Handoff"]
    EVID --> VALIDATION["Validation runtime"]
    APPROVAL --> LIFECYCLE["WorkUnit lifecycle"]
    HOLD --> LIFECYCLE
    VALIDATE --> VALIDATION

    CONTRACTS --> MAOS
    AGENTS --> MAOS
    HANDOFF --> MAOS
    VALIDATION --> MAOS
    LIFECYCLE --> MAOS
```

## Migration rules

1. MultiAgentOS remains the single execution runtime.
2. PetTarotReading's `.agent-os` directory is not copied.
3. Existing WorkUnit, planning, delegation, orchestration, state, checkpoint, MCP, and model-routing systems remain authoritative.
4. Governance is expressed as provider-neutral Python contracts and runtime checks.
5. Agent roles are catalog entries, not a second orchestration engine.
6. Deterministic validators decide machine-checkable facts; agents provide work and evidence.
7. Release and irreversible actions remain behind explicit human approval.
8. HOLD prevents silent resume, reset, revert, or rewrite.

## Role mapping

| PetTarotReading role | MultiAgentOS role | Primary capability |
| --- | --- | --- |
| File Picker | `file-picker` | discovery |
| Planner | `planner` | planning |
| Web Researcher | `web-researcher` | research |
| Editor | `editor` | bounded editing |
| Executor | `executor` | process / execution |
| Terminal Monitor | `terminal-monitor` | runtime monitoring |
| Reviewer | `reviewer` | review |
| Browser Agent | `browser-agent` | browser validation |
| Debugger | `debugger` | bounded debugging |

The existing MultiAgentOS `tester` and platform specialists remain available; these nine roles add the execution-governance vocabulary rather than replacing existing specialists.

## Smallest-sufficient routing

```mermaid
flowchart LR
    SIMPLE["Simple development"] --> P1["Planner"]
    P1 --> E1["Editor"]
    E1 --> X1["Executor"]
    X1 --> R1["Reviewer"]

    RESEARCH["External API / SDK"] --> P2["Planner"]
    P2 --> W2["Web Researcher"]
    W2 --> E2["Editor"]
    E2 --> X2["Executor"]
    X2 --> R2["Reviewer"]

    UI["Web UI"] --> P3["Planner"]
    P3 --> E3["Editor"]
    E3 --> X3["Executor"]
    X3 --> B3["Browser Agent"]
    B3 --> R3["Reviewer"]

    FAILURE["Failure / bug"] --> P4["Planner"]
    P4 --> X4["Executor"]
    X4 --> T4["Terminal Monitor"]
    T4 --> D4["Debugger"]
    D4 --> X5["Executor"]
    X5 --> R4["Reviewer"]
```

Routing is a template, not a requirement to invoke every role. The runtime should select the smallest sufficient path.

## Governance boundary

```mermaid
flowchart TB
    WU["WorkUnit"] --> S["ScopeLock"]
    WU --> PERM["Agent permissions"]
    WU --> ART["Artifacts"]
    WU --> EVID["Evidence"]
    WU --> LIFE["Lifecycle"]

    S --> ENFORCE["Runtime enforcement"]
    PERM --> ENFORCE
    ART --> ENFORCE
    EVID --> ENFORCE
    LIFE --> ENFORCE

    ENFORCE --> RESULT{"Deterministic result"}
    RESULT --> PASS["PASS / VERIFIED"]
    RESULT --> WARN["WARN"]
    RESULT --> FAIL["FAIL / BLOCKED"]
    RESULT --> APPROVAL["READY_FOR_APPROVAL"]
    APPROVAL --> HUMAN["Human approval"]
```

## Implementation order

1. Introduce provider-neutral `ScopeLock` and `EvidenceRecord` contracts.
2. Extend `PlanStep` and `WorkUnit` with bounded scope/governance metadata.
3. Add the nine execution roles to the native Agent catalog.
4. Add HOLD and approval-aware lifecycle guards.
5. Add deterministic scope/evidence validation to the validation runtime.
6. Add routing templates and governance documentation.
7. Update tests and localized architecture documentation.

This order deliberately reuses existing MultiAgentOS approval, artifact, handoff, state, and validation infrastructure instead of creating parallel subsystems.

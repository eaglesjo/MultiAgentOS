# Governance Runtime

MultiAgentOS keeps orchestration in the native Agent Execution Runtime while applying PetTarotReading's governance rules at explicit runtime boundaries.

## Execution and approval boundary

~~~mermaid
flowchart TB
    TASK["Task"] --> WU["WorkUnit"]
    WU --> SCOPE["Scope Lock"]
    WU --> ROUTE["Smallest Sufficient Route"]
    ROUTE --> PLAN["Native PlanStep"]
    PLAN --> EXEC["Orchestrator / Agent Execution"]
    EXEC --> ART["Artifact"]
    EXEC --> EVID["Evidence"]
    ART --> VALID["GovernanceRuntime"]
    EVID --> VALID

    VALID -->|non-release impact| DONE["COMPLETED"]
    VALID -->|release impact + verified evidence| READY["READY_FOR_APPROVAL"]
    READY -->|explicit human approval| APPROVED["USER_APPROVED"]
    APPROVED -->|explicit release authorization| RELEASED["RELEASED"]
    RELEASED --> DONE

    WU -->|HOLD| HOLD["HOLD"]
    HOLD -->|authorized resume| EXEC
    HOLD -->|terminal safety stop| BLOCKED["BLOCKED"]
~~~

## Smallest sufficient execution routes

~~~mermaid
flowchart TD
    TASK["Task"] --> TYPE{"Work Type"}

    TYPE -->|development| SIMPLE["File Picker → Planner → Editor → Executor → Reviewer"]
    TYPE -->|external research| RESEARCH["File Picker → Planner → Web Researcher → Editor → Executor → Reviewer"]
    TYPE -->|web UI| WEB["File Picker → Planner → Editor → Executor → Browser Agent → Reviewer"]
    TYPE -->|failure| FAILURE["File Picker → Planner → Executor → Terminal Monitor → Debugger → Executor → Reviewer"]
~~~

The route is represented by native PlanStep objects and is executed by the existing Orchestrator; no second orchestration engine is introduced.

## Governance responsibilities

| Boundary | Deterministic responsibility |
| --- | --- |
| WorkUnit creation | Scope, target, environment and release impact |
| Planning | Plan validation and child-scope containment |
| Execution | Existing Agent Execution Runtime |
| Artifact handoff | Artifact contract validation |
| Evidence | WorkUnit ownership and verified-evidence checks |
| HOLD | No execution without explicit resume authorization |
| Release impact | Stop at READY_FOR_APPROVAL |
| Human gate | USER_APPROVED requires explicit authorization |
| Release | RELEASED requires explicit authorization |

## Safety rule

Agents do not receive release authority. The governance runtime only records the explicit approval/release boundary; the caller remains responsible for the external irreversible action.

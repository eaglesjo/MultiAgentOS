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


## Specialist taxonomy routing

Governance and specialist responsibilities are orthogonal.

~~~mermaid
flowchart TB
    TASK["Task"]

    TASK --> GOV["Governance / Execution"]
    TASK --> SPEC["Specialist"]

    GOV --> PICKER["File Picker"]
    GOV --> PLAN["Planner"]
    GOV --> EDIT["Editor"]
    GOV --> EXEC["Executor"]
    GOV --> REVIEW["Reviewer"]

    SPEC --> RESEARCH["Research"]
    SPEC --> DEVELOPMENT["Development"]
    SPEC --> UI["UI"]

    RESEARCH --> DEV_R["Development Research"]
    RESEARCH --> UI_R["UI Research"]

    DEV_R --> REACT_R["React"]
    DEV_R --> RN_R["React Native"]
    DEV_R --> ANDROID_R["Android"]
    DEV_R --> IOS_R["iOS"]

    UI_R --> WEB_R["Web UI / React"]
    UI_R --> RN_UI_R["React Native UI"]
    UI_R --> ANDROID_UI_R["Android UI"]
    UI_R --> IOS_UI_R["iOS UI"]

    DEVELOPMENT --> REACT_D["React Developer"]
    DEVELOPMENT --> RN_D["React Native Developer"]
    DEVELOPMENT --> ANDROID_D["Android Developer"]
    DEVELOPMENT --> IOS_D["iOS Developer"]
~~~

The runtime composes these dimensions rather than making specialist agents compete with governance roles.

### Development routing

~~~mermaid
flowchart LR
    TASK["Development"] --> PLAN["Planner"]
    PLAN --> RESEARCH["Platform Development Research"]
    RESEARCH --> DEV["Platform Developer"]
    DEV --> EDIT["Editor"]
    EDIT --> EXEC["Executor"]
    EXEC --> REVIEW["Reviewer"]
~~~

### UI routing

~~~mermaid
flowchart LR
    TASK["UI"] --> PLAN["Planner"]
    PLAN --> RESEARCH["Platform UI Research"]
    RESEARCH --> UI["Platform UI Specialist"]
    UI --> EDIT["Editor"]
    EDIT --> EXEC["Executor"]
    EXEC --> VALIDATE["Platform UI Validation"]
    VALIDATE --> REVIEW["Reviewer"]
~~~

For Web UI, Browser Agent is a validation capability under the Web branch rather than the UI root.

## Safety rule

Agents do not receive release authority. The governance runtime only records the explicit approval/release boundary; the caller remains responsible for the external irreversible action.

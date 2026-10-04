# Agent Execution Runtime Agent Catalog

MultiAgentOS separates **Governance / Execution roles** from **Specialist taxonomy**. Governance agents control how work is executed; specialist agents describe what the work is about.

## Taxonomy

~~~mermaid
flowchart TB
    ROOT["Agent System"]

    ROOT --> GOV["Governance / Execution"]
    ROOT --> RESEARCH["Research"]
    ROOT --> UI["UI"]
    ROOT --> DEV["Development"]

    GOV --> PICKER["File Picker"]
    GOV --> PLANNER["Planner"]
    GOV --> EDITOR["Editor"]
    GOV --> EXEC["Executor"]
    GOV --> MONITOR["Terminal Monitor"]
    GOV --> REVIEW["Reviewer"]
    GOV --> DEBUG["Debugger"]
    GOV --> BROWSER["Browser Agent"]

    RESEARCH --> DEV_R["Development Research"]
    RESEARCH --> UI_R["UI Research"]

    DEV_R --> REACT_R["React"]
    DEV_R --> RN_R["React Native"]
    DEV_R --> ANDROID_R["Android"]
    DEV_R --> IOS_R["iOS"]

    UI_R --> WEB_UI_R["Web UI / React"]
    UI_R --> RN_UI_R["React Native UI"]
    UI_R --> ANDROID_UI_R["Android UI / Compose"]
    UI_R --> IOS_UI_R["iOS UI / SwiftUI"]

    DEV --> REACT_D["React Developer"]
    DEV --> RN_D["React Native Developer"]
    DEV --> ANDROID_D["Android Developer"]
    DEV --> IOS_D["iOS Developer"]

    UI --> WEB_UI["Web UI"]
    UI --> RN_UI["React Native UI"]
    UI --> NATIVE["Native UI"]
    NATIVE --> ANDROID_UI["Android UI"]
    NATIVE --> IOS_UI["iOS UI"]

    BROWSER -. capability .-> WEB_UI
~~~

The same agent can carry capabilities and tools while its taxonomy remains explicit in AgentContract.taxonomy.

## Agent contract dimensions

~~~mermaid
flowchart LR
    AGENT["AgentContract"]

    AGENT --> LAYER["layer"]
    AGENT --> DOMAIN["domain"]
    AGENT --> PLATFORM["platform"]
    AGENT --> TECHNOLOGY["technology"]
    AGENT --> SPECIALIZATION["specialization"]
    AGENT --> PARENT["parent_id"]

    LAYER --> GOVERNANCE["governance"]
    LAYER --> SPECIALIST["specialist"]
~~~

The dimensions are intentionally orthogonal:

- **layer** — governance or specialist
- **domain** — development, UI, research, etc.
- **platform** — web, React Native, Android, iOS
- **technology** — React, Kotlin, Jetpack Compose, Swift, SwiftUI, etc.
- **specialization** — development research or UI research
- **parent_id** — hierarchy such as ui-agent → ui-native → ui-android

This avoids treating Editor, React Developer, Android Developer, and UI Researcher as competing roles at the same level.

## Development specialists

Development is explicitly platform-oriented:

| Platform | Development agent | Primary technology |
| --- | --- | --- |
| Web | react-developer | React |
| Cross-platform | react-native-developer | React Native |
| Android | android-developer | Kotlin |
| iOS | ios-developer | Swift |

## UI specialists

UI is a hierarchy rather than a flat web_ui role:

~~~mermaid
flowchart TB
    UI["UI Agent"]

    UI --> WEB["Web"]
    UI --> CROSS["Cross-platform"]
    UI --> NATIVE["Native"]

    WEB --> REACT["React"]
    CROSS --> RN["React Native"]

    NATIVE --> ANDROID["Android"]
    NATIVE --> IOS["iOS"]

    ANDROID --> COMPOSE["Jetpack Compose"]
    IOS --> SWIFTUI["SwiftUI"]
~~~

browser-agent is a Web validation capability. It is not the root of the UI hierarchy.

## Research specialists

Research is split into development research and UI research.

~~~mermaid
flowchart TB
    R["Research"]

    R --> DEV["Development Research"]
    R --> UI["UI Research"]

    DEV --> REACT["React"]
    DEV --> RN["React Native"]
    DEV --> ANDROID["Android"]
    DEV --> IOS["iOS"]

    UI --> WEB["Web UI / React"]
    UI --> RN_UI["React Native UI"]
    UI --> ANDROID_UI["Android UI / Compose"]
    UI --> IOS_UI["iOS UI / SwiftUI"]
~~~

Development research checks implementation-facing sources before development. UI research checks platform UI guidance, accessibility, layout, framework APIs, and current design guidance before UI implementation.

The research specialists prefer authoritative sources. React currently documents 19.3 as the latest version. citeturn0search20 React Native documents the current architecture, including Fabric/rendering and the New Architecture. citeturn0search3turn0search17 Android Developers describes Compose as the modern Android UI toolkit and continues to support Views for existing applications. citeturn1search0turn1search2 Apple documents SwiftUI, UIKit interoperability, and current Human Interface Guidelines. citeturn0search8turn0search1turn0search9

## Composed execution route

A development task with a known platform can require platform-specific research before implementation:

~~~mermaid
flowchart LR
    TASK["Development Task"] --> PLAN["Planner"]
    PLAN --> RESEARCH["Platform Development Research"]
    RESEARCH --> DEV["Platform Developer"]
    DEV --> EDITOR["Editor"]
    EDITOR --> EXEC["Executor"]
    EXEC --> REVIEW["Reviewer"]
~~~

For UI work:

~~~mermaid
flowchart LR
    TASK["UI Task"] --> PLAN["Planner"]
    PLAN --> RESEARCH["Platform UI Research"]
    RESEARCH --> UI["UI Specialist"]
    UI --> EDITOR["Editor"]
    EDITOR --> EXEC["Executor"]
    EXEC --> VALIDATE["Browser / Platform UI Test"]
    VALIDATE --> REVIEW["Reviewer"]
~~~

The runtime composes these specialist stages with the existing governance stages instead of creating a second orchestration system.

## Existing profile specialists

The existing React Native, Android Native, and iOS Native profile specialists remain available for compatibility. Their taxonomy now maps them into the same platform/domain model.

Agents carry capabilities, tools, permissions, and model preferences without embedding a vendor-specific AI.

Handoff artifacts carry summary, files/artifacts, findings, and source/target identity.

ReviewPanel supports multiple independent reviewers and requires all reviewers to approve before consensus is approved.

ReviewPanel executes independent reviewers in parallel by default and supports sequential mode for deterministic adapters.

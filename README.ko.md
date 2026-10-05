
# MultiAgentOS

> **로컬 우선(Local-first) 멀티 에이전트 소프트웨어 개발용 Agent Execution Runtime**

MultiAgentOS는 실제 소프트웨어 개발 작업을 오케스트레이션하기 위한 **벤더 중립적 Agent Execution Runtime**입니다.

AI 에이전트가 무엇을 판단하고 제안하는지와 런타임이 무엇을 실제로 실행하도록 허용하는지를 분리합니다. 작업은 통제된 WorkUnit으로 표현되고, 적합한 Agent와 Model에 라우팅된 뒤 명시적인 실행 경계를 통해 수행되며, 검증·리뷰·handoff를 거쳐 완료됩니다.

**현재 릴리스: 0.5.0**

---

## 왜 MultiAgentOS인가?

AI 클라이언트와 모델은 추론, 계획 수립, 코드 및 변경안 생성에 강합니다. 실제 개발 환경에서는 여기에 더해 책임 경계, 에이전트 라우팅, 실행 상태, 검증, 복구, 감사 가능성이 필요합니다.

MultiAgentOS는 이러한 실행 모델을 제공합니다.

~~~mermaid
flowchart TB
    TASK["개발 작업"] --> PLAN["계획"]
    PLAN --> DELEGATE["위임"]
    DELEGATE --> ASSIGN["Agent × Model 할당"]
    ASSIGN --> EXEC["실행"]
    EXEC --> VERIFY["검증"]
    VERIFY --> REVIEW["리뷰"]
    REVIEW --> HANDOFF["Handoff"]
    HANDOFF --> DONE["완료"]
~~~

런타임은 특정 모델 벤더, IDE, CLI, 호스팅 에이전트 플랫폼 또는 코딩 클라이언트에 종속되지 않습니다.

---

## 0.5.0 핵심 변화

0.5.0은 **에이전트 오케스트레이션과 전문 에이전트 런타임 아키텍처**를 정식 구조로 확립한 버전입니다.

### 핵심 실행 모델

표준 개발 루프는 다음과 같습니다.

**이해 → 계획 → 위임 → 오케스트레이션 → 실행 → 검증 → 리뷰 → 학습/Handoff**

오케스트레이션은 핵심 아키텍처입니다. 전문 에이전트는 오케스트레이션 흐름 안에 조합되며, 별도의 실행 시스템을 만들지 않습니다.

### Agent Taxonomy

MultiAgentOS는 두 개의 근본적인 계층을 구분합니다.

- **Governance / Execution** — 작업을 어떻게 라우팅하고, 편집하고, 실행하고, 모니터링하고, 디버깅하고, 리뷰할지를 통제합니다.
- **Specialist** — 해당 작업에 필요한 기술 분야와 전문 책임을 나타냅니다.

실제 개발 책임이 필요하다면 전문 에이전트를 추가할 수 있습니다. 따라서 에이전트 카탈로그는 최소 개수로 고정하지 않고 실제 개발 역할에 맞춰 확장할 수 있도록 설계되어 있습니다.

~~~mermaid
flowchart TB
    TASK["작업"]
    TASK --> GOV["Governance / Execution"]
    TASK --> SPEC["Specialists"]
    GOV --> PLAN["Planner"]
    GOV --> EDIT["Editor"]
    GOV --> EXEC["Executor"]
    GOV --> REVIEW["Reviewer"]
    GOV --> DEBUG["Debugger"]
    GOV --> BROWSER["Browser Agent"]
    SPEC --> RESEARCH["Research"]
    SPEC --> DEVELOPMENT["Development"]
    SPEC --> UI["UI / UX"]
    SPEC --> QUALITY["Quality"]
    SPEC --> OPS["Operations"]
~~~

### 확장된 전문 분야

0.5.0에서는 완성도 있는 소프트웨어 제품을 개발하는 데 필요한 주요 책임 영역으로 전문 에이전트 카탈로그를 확장했습니다.

| 영역 | 전문 에이전트 |
| --- | --- |
| 아키텍처 | software-architect |
| Backend / API / Data | backend-developer, api-developer, database-engineer |
| UX / UI | ux-designer, ui-designer, design-system-specialist, accessibility-specialist |
| 품질 | qa-engineer, security-engineer, performance-engineer |
| 운영 | devops-engineer |
| 플랫폼 개발 | react-developer, react-native-developer, android-developer, ios-developer |
| 플랫폼 리서치 | React, React Native, Android, iOS 개발 리서치 |
| UI 리서치 | Web/React, React Native, Android/Compose, iOS/SwiftUI 리서치 |

이 역할들은 기존 역할을 대체하지 않는 **추가적인 전문 역할**입니다. 또한 새로운 오케스트레이션 계층을 만들지 않습니다.

---

## 오케스트레이션

개발 WorkUnit은 명시적인 실행 단계를 따라 이동합니다.

~~~mermaid
flowchart LR
    WU["WorkUnit"] --> ROUTE["라우팅"]
    ROUTE --> ASSIGN["Agent × Model 할당"]
    ASSIGN --> EXEC["실행"]
    EXEC --> VERIFY["검증"]
    VERIFY --> REVIEW["리뷰"]
    REVIEW --> HANDOFF["Handoff"]
    HANDOFF --> COMPLETE["완료"]
~~~

오케스트레이션 계약은 다음을 책임집니다.

1. 작업 목표를 정의합니다.
2. 호환 가능한 Agent × Model 할당을 결정합니다.
3. 라우팅이 성공하기 전에는 실행이 시작되지 않도록 합니다.
4. 실행 어댑터를 호출합니다.
5. 필요할 경우 결과를 검증합니다.
6. 필요할 경우 결과를 리뷰합니다.
7. 검증된 작업을 다음 단계로 handoff합니다.
8. 실행·검증·리뷰 실패를 명시적인 실패 상태로 전환합니다.

Orchestrator, DelegationEngine, MultiAgentWorkflow가 이 책임들을 조합하며, 특정 AI 제공업체에 런타임을 종속시키지 않습니다.

자세한 내용은 [Orchestration](docs/ORCHESTRATION.md)을 참고하세요.

---

## 구현 전에 리서치

플랫폼에 종속된 개발 작업은 구현 전에 최신 기술 정보를 확인하는 단계를 포함할 수 있습니다.

~~~mermaid
flowchart LR
    TASK["플랫폼 개발 작업"] --> PLAN["Planner"]
    PLAN --> RESEARCH["플랫폼 리서치"]
    RESEARCH --> SPECIALIST["플랫폼 전문 에이전트"]
    SPECIALIST --> EDIT["Editor"]
    EDIT --> EXEC["Executor"]
    EXEC --> REVIEW["Reviewer"]
~~~

Development Research는 현재 지원되는 API, 호환성, deprecated API, 마이그레이션 가이드, 구현 패턴 등을 확인합니다.

UI Research는 플랫폼 UI 가이드, 접근성, 레이아웃, 프레임워크 API, 상호작용 패턴, 시각적 검증 기준 등을 확인합니다.

리서치는 별도의 실행 체계가 아니라 동일한 오케스트레이션 모델 안에서 수행되는 전문 책임입니다.

---

## Agent × Model 실행

Agent 선택과 Model 선택은 서로 분리되어 있지만 하나의 실행 할당으로 조정됩니다.

~~~mermaid
flowchart TB
    WORK["WorkUnit"] --> AGENT["Agent 선택"]
    AGENT --> MODEL["Model 결정"]
    MODEL --> ASSIGN["Agent × Model 할당"]
    ASSIGN --> DECISION["Execution Decision"]
    DECISION --> RUNTIME["Agent Execution Runtime"]
~~~

Agent는 capability, tool, permission, 지원 Model ID, metadata, taxonomy, scope awareness를 선언할 수 있습니다.

Model 결정은 capability, health, quota 등의 정보를 활용하면서도 provider-neutral runtime contract를 유지할 수 있습니다.

---

## 실행 거버넌스

MultiAgentOS는 실행 권한을 명시적인 런타임 경계 뒤에 둡니다.

~~~mermaid
flowchart TB
    INTENT["Agent 의도"] --> REQUEST["실행 요청"]
    REQUEST --> POLICY["Runtime Policy"]
    POLICY --> FS["Filesystem"]
    POLICY --> PATCH["Patch"]
    POLICY --> PROCESS["Process"]
    POLICY --> GIT["Git"]
    POLICY --> PROJECT["프로젝트 상태"]
~~~

런타임은 scope, permission, authorization, execution state를 통제하고 집행합니다.

MCP와 Tool capability는 **실행 경계**로 유지됩니다. 오케스트레이션을 대체하는 별도의 제품 아키텍처 계층으로 확장하지 않습니다.

쓰기 및 process capability는 필요한 프로젝트에서 명시적으로 활성화해야 하는 런타임 책임입니다.

---

## 복구·Replay·Idempotency

0.5.0은 0.4.x 계열에서 구축된 런타임 안전성 계약을 유지합니다.

### Durable execution state

WorkUnit 상태는 안전한 재개에 필요한 정보를 지속적으로 보존합니다. 여기에는 작업 범위, 대상, 실행 환경, artifact 분류, release 영향, hold 상태 등이 포함됩니다.

### 복구 시 실행 주체 식별

복구된 tool invocation에서도 다음 감사 식별자를 유지합니다.

- decision_id
- agent_id
- model_id
- invocation_id
- idempotency_key

### Replay Policy

Replay는 명시적인 정책으로 분류됩니다.

| 정책 | 의미 |
| --- | --- |
| **SAFE** | 자동 복구 replay 허용 |
| **REVIEW_REQUIRED** | replay 전에 사람의 승인이 필요 |
| **NEVER** | replay 금지 |

Replay 안전성은 단순히 읽기 작업인지 쓰기 작업인지와 동일한 개념이 아닙니다.

### Idempotency

Tool invocation은 안정적인 idempotency key를 가질 수 있습니다. 동일 WorkUnit에서 이미 사용된 idempotency key를 다시 사용하려는 요청은 동일 작업의 중복 실행을 막기 위해 런타임에서 거부합니다.

단, idempotency key가 존재한다는 사실만으로 분산 환경의 exactly-once 실행을 보장한다고 주장하지 않습니다. 외부 시스템의 부작용까지 제어하려면 해당 시스템 역시 idempotency key를 실제로 지원하고 준수해야 합니다.

---

## 로컬 우선 프로젝트 실행

MultiAgentOS는 실제 프로젝트 작업 공간을 중심으로 설계됩니다.

~~~mermaid
flowchart TB
    CLIENT["AI Client / Coding Agent"] --> RUNTIME["MultiAgentOS Agent Execution Runtime"]
    RUNTIME --> PROJECT["로컬 프로젝트"]
    PROJECT --> GIT["Git"]
    GIT --> GITHUB["GitHub Repository"]
~~~

Repository는 지속적인 소스 이력과 협업을 담당하고, 로컬 런타임은 실제 working tree에 대한 통제된 접근을 담당합니다.

두 경로는 서로 대체되는 것이 아니라 서로 보완하는 실행 표면입니다.

---

## 프로젝트 초기화

런타임 설치:

~~~bash
python3 -m pip install "multiagentos[mcp-http]"
~~~

프로젝트 초기화:

~~~bash
cd your-project
multiagentos init . --component all
multiagentos status .
~~~

통제된 작업 실행:

~~~bash
multiagentos run \
  --path . \
  --objective "run tests" \
  -- python -m unittest discover -s tests -v
~~~

클라이언트가 런타임 경계를 사용해야 한다면 로컬 MCP endpoint를 실행할 수 있습니다.

~~~bash
multiagentos mcp serve-http --path .
~~~

프로젝트에서 명시적으로 write access가 필요한 경우:

~~~bash
multiagentos mcp serve-http \
  --path . \
  --allow-write
~~~

기본 endpoint:

~~~text
http://127.0.0.1:8000/mcp
~~~

프로젝트 설정은 다음 위치에 저장됩니다.

~~~text
.multiagentos/
├── components.json
├── execution.json
├── chat.json
├── agents.json
└── state/
~~~

Credential과 provider API key는 프로젝트 설정에 저장하지 않습니다.

---

## 프로젝트별 런타임 서비스

여러 프로젝트를 서로 독립적으로 관리할 수 있습니다.

~~~bash
multiagentos mcp install \
  --path /absolute/path/to/project1 \
  --port 8000 \
  --allow-write

multiagentos mcp install \
  --path /absolute/path/to/project2 \
  --port 8001 \
  --allow-write
~~~

관리 중인 서비스를 확인하거나 제거합니다.

~~~bash
multiagentos mcp status --path /absolute/path/to/project1
multiagentos mcp uninstall --path /absolute/path/to/project1
~~~

macOS와 Windows에서 사용자 단위 OS 네이티브 서비스 관리 등 프로젝트별 런타임 수명주기 관리를 지원합니다.

---

## 검증과 릴리스 게이트

0.5.0은 release candidate가 저장소의 릴리스 검증을 통과한 뒤 정식 릴리스되었습니다.

릴리스 게이트에는 다음 검증이 포함되었습니다.

- 전체 contract test suite
- 설치 smoke test
- MCP Streamable HTTP inspection
- package build 및 artifact 검증
- Windows x64, Ubuntu amd64, macOS Intel x64, macOS ARM64 native package 검증
- 확장된 specialist catalog contract 검증
- recovery, replay policy, tool identity, idempotency 회귀 검증

v0.5.0 tag가 이 버전의 공식 릴리스 기준점입니다.

현재 테스트 실행:

~~~bash
python -m unittest discover -s tests -v
~~~

저장소 전체 릴리스 검증의 권위 있는 실행 환경은 GitHub Actions입니다.

---

## 문서

### 아키텍처

- [오케스트레이션](docs/ORCHESTRATION.md)
- [Agent Taxonomy 및 Routing](docs/AGENT_TAXONOMY.md)
- [Agent Catalog](docs/AGENT_CATALOG.md)
- [Architecture Decisions](docs/ARCHITECTURE_DECISIONS.md)

### 런타임 및 프로젝트 설정

- [Getting Started](docs/GETTING_STARTED.md)
- [Project Installation](docs/PROJECT_INSTALLATION.md)
- [Agent Execution Runtime Connection Guide](docs/AGENT_EXECUTION_RUNTIME_CONNECTIONS.md)
- [Agent Execution Runtime GitHub Connection](docs/AGENT_EXECUTION_RUNTIME_GITHUB_CONNECTION.md)

### 선택적 연결 및 플랫폼 연동

- [Secure MCP Tunnel Setup](docs/MCP_TUNNEL.md)
- [macOS MCP Service](docs/MACOS_MCP_SERVICE.md)
- [macOS Tunnel Service](docs/MACOS_TUNNEL_SERVICE.md)
- [ChatGPT Client Capability Matrix](docs/CHATGPT_CLIENT_CAPABILITIES.md)

MCP, Tool, 원격 연결 관련 문서는 현재 제공되는 실행 경계와 연동 방식을 설명합니다. 이 문서들이 별도의 제품 아키텍처 계층을 추가로 정의하는 것은 아닙니다.

영문 README를 기술 내용의 기준 문서로 유지하며, 한국어 README는 동일한 구조와 의미를 자연스러운 한국어로 제공합니다.

**[English README](README.md)**

---

## 릴리스 이력

전체 릴리스 이력은 [CHANGELOG.md](CHANGELOG.md)를 참고하세요.

## License

[LICENSE](LICENSE)를 참고하세요.

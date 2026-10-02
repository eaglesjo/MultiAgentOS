# MultiAgentOS

> **Cost-Free Multi-Agent Development Orchestration**

MultiAgentOS는 **Agent Execution Runtime**을 중심으로 하는 로컬 우선 AI 개발 오케스트레이션 플랫폼입니다.

Cost-Free 기본 경로에서는 **별도의 유료 AI API Key가 필요하지 않습니다.** MultiAgentOS는 이미 사용할 수 있는 AI 클라이언트와 GitHub, 로컬 프로젝트를 연결하고 실행 권한은 Agent Execution Runtime 안에 유지합니다.

## MultiAgentOS가 하는 일

MultiAgentOS는 **AI 협업**과 **실행 권한**을 분리합니다.

- **ChatGPT Web** — 현재 검증된 전체 개발 진입점(GitHub + 로컬 MCP)
- **ChatGPT Mobile** — 현재 검증된 GitHub 전용 개발 진입점
- **로컬 MCP Client** — 독립적인 로컬 연결 경로
- **ChatGPT Codex Connector** — 원격 GitHub Repository 연결
- **Agent Execution Runtime MCP** — 로컬 프로젝트 연결
- **Orchestrator** — 전체 멀티 에이전트 협업 조정
- **MultiAgentWorkflow** — Developer → Tester → Reviewer 실행
- **Agent Execution Runtime** — 권한 및 실행의 최종 경계

Agent는 의도, 계획, 결과를 제공하지만 filesystem, process, patch, Git 실행 권한을 직접 소유하지 않습니다.

## 아키텍처

```text
                         Web Browser
                              |
                              v
                         ChatGPT Web
                         /          \
                        v            v
       ChatGPT Codex Connector   Agent Execution Runtime MCP
                    |                  |
                    v                  v
            GitHub Repository      Local Project

                         ChatGPT Mobile
                              |
                              v
                    ChatGPT Codex Connector
                              |
                              v
                       GitHub Repository
                    |                   |
                    +---------+---------+
                              |
                              v
                        MultiAgentOS
                              |
                              v
                         Orchestrator
                              |
                              v
                    MultiAgentWorkflow
                     /       |       \
               Developer   Tester   Reviewer
                              |
                              v
                         Verification
                              |
                              v
                           Agent Execution Runtime
```

### ChatGPT 클라이언트 검증 범위

현재 MultiAgentOS 개발 환경에서 실제 확인한 연결 범위는 다음과 같습니다.

| 클라이언트 | GitHub Repository | 로컬 MCP / 로컬 프로젝트 | 상태 |
| --- | --- | --- | --- |
| **ChatGPT Web** | 가능 | 가능 | **검증 완료** |
| **ChatGPT Mobile** | 가능 | 불가 | **검증 완료** |
| **ChatGPT Desktop** | 미검증 | 미검증 | 현재 릴리스 범위 밖 |

> **중요:** 현재 검증 환경에서는 ChatGPT Web이 GitHub와 로컬 MultiAgentOS MCP를 모두 사용할 수 있습니다. 반면 ChatGPT Mobile에서는 GitHub 연결은 가능하지만 로컬 MCP 접근은 사용할 수 없습니다. 이 표는 현재 검증된 클라이언트/연결 조합을 기록한 것이며 모든 ChatGPT 계정이나 제품 구성에 대한 보편적 보장을 의미하지 않습니다.

### 책임 경계

| 구성 요소 | 책임 |
| --- | --- |
| **ChatGPT Web** | GitHub + 로컬 MCP를 사용할 수 있는 현재의 전체 개발 진입점 |
| **ChatGPT Mobile** | GitHub만 사용하는 현재의 모바일 개발 진입점 |
| **ChatGPT Codex Connector** | 원격 GitHub Repository 접근 |
| **Agent Execution Runtime MCP** | 로컬 프로젝트 연결 |
| **Secure MCP Tunnel** | 로컬 MCP에 직접 접근할 수 없는 외부 클라이언트를 위한 선택적 원격 연결 |

| **MultiAgentOS** | Agent 계약, 라우팅, 상태, 오케스트레이션 |
| **Orchestrator** | 전체 협업 조정 |
| **MultiAgentWorkflow** | 단계, handoff, review, rework 의미론 |
| **Agent Execution Runtime** | 권한 및 실행 제어 |

## 멀티 에이전트 워크플로

```text
Request
  |
  v
Orchestrator
  |
  v
MultiAgentWorkflow
  |
  +--> Developer
  |
  +--> Tester
  |
  +--> Reviewer
  |
  +--> 필요한 경우 Rework
  |
  v
Verification
  |
  v
Completed / Failed
```

`Orchestrator.run_workflow()`가 안정적인 상위 오케스트레이션 진입점입니다. `MultiAgentWorkflow`가 구체적인 stage, handoff, review, rework 의미론을 담당하며, `MultiAgentRuntime`은 애플리케이션/runtime adapter로서 이 오케스트레이션 경계를 사용합니다.

Agent Execution Runtime은 permission, filesystem, patch, process, Git, verification을 담당하는 실행 경계로 유지됩니다.

## 연결 모델

### ChatGPT Web — GitHub 경로

```text
ChatGPT Web
    |
    v
ChatGPT Codex Connector
    |
    v
GitHub Repository
```

### ChatGPT Web — 로컬 프로젝트 경로

```text
ChatGPT Web
    |
    v
127.0.0.1:8000/mcp
    |
    v
MultiAgentOS MCP
    |
    v
Local Project
```

로컬 Agent Execution Runtime MCP Server가 기본 경로입니다. 현재 검증 환경에서는 ChatGPT Web이 이 로컬 MCP를 직접 사용할 수 있으며, ChatGPT Mobile에서는 사용할 수 없습니다. 로컬 MCP Client도 독립적으로 사용할 수 있습니다. Secure MCP Tunnel은 기본 경로에 필요하지 않습니다.

Secure MCP Tunnel은 외부에서 로컬 MCP에 접근해야 할 때만 사용하는 선택적 연결 계층입니다.

## 용어 체계

**Agent Execution Runtime**을 로컬 실행·권한 경계의 공식 설명 명칭으로 사용합니다.

## Cost-Free 기본 경로

핵심은 간단합니다.

> **MultiAgentOS Cost-Free 기본 경로에는 별도의 유료 AI API Key가 필요하지 않습니다.**

또한 다음도 기본적으로 필요하지 않습니다.

- 별도의 Agent API 구독
- MultiAgentOS SaaS 구독
- Tunnel을 위한 두 번째 MCP Server

단, 실제 사용하는 AI 서비스의 플랜 및 사용량 제한은 그대로 적용됩니다. Cost-Free는 MultiAgentOS의 런타임 비용 구조를 의미하며 AI 서비스의 무제한 사용을 의미하지 않습니다.

### 검증된 기본 기능

- Agent Execution Runtime MCP stdio 초기화 및 tool discovery
- filesystem READ / WRITE
- `patch.apply`
- `shell.run`
- local MCP/runtime tests
- runtime health/readiness
- Secure MCP Tunnel readiness

자세한 검증 기록은 [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md)을 참고하세요.

## 빠른 시작

### 설치

로컬 Streamable HTTP MCP를 사용하려면:

```bash
python3 -m pip install "multiagentos[mcp-http]"
```

별도의 OpenAI API Key는 필요하지 않습니다.

### 프로젝트 초기화

```bash
cd your-project
multiagentos init . --component all
multiagentos status .
```

### 로컬 작업 실행

```bash
multiagentos run --path . --objective "run tests" -- python -m unittest discover -s tests -v
```

### Chat Agent 세션 시작

```bash
multiagentos chat --path . --objective "inspect the current project"
```

### 로컬 MCP Server 실행

```bash
multiagentos mcp serve-http --path . --allow-write
```

macOS에서 한 번 설정하고 로그인/재부팅 후 자동 실행하려면:

```bash
multiagentos mcp install --path . --allow-write
```

상태 확인/제거:

```bash
multiagentos mcp status
multiagentos mcp uninstall
```

## 설정

프로젝트 설정은 `.multiagentos/` 아래에 저장됩니다.

초기화 과정에서 다음 파일을 설치할 수 있습니다.

- `components.json` — 선택한 component
- `execution.json` — execution Agent/Model 선택
- `chat.json` — Chat Agent 선택
- `agents.json` — multi-agent catalog
- `state/` 및 필요한 session/checkpoint 데이터

Credential과 provider API key는 프로젝트 설정에 기록하지 않습니다.

## 검증

```bash
python -m unittest discover -s tests -v
```

GitHub Actions에서도 저장소 CI를 검증합니다.

## 문서

- [Getting Started](docs/GETTING_STARTED.md)
- [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md)
- [ChatGPT Client Capability Matrix](docs/CHATGPT_CLIENT_CAPABILITIES.md)
- [Agent Execution Runtime Connection Guide](docs/AGENT_EXECUTION_RUNTIME_CONNECTIONS.md)
- [Secure MCP Tunnel Setup](docs/MCP_TUNNEL.md)
- [Agent Execution Runtime GitHub Connection](docs/AGENT_EXECUTION_RUNTIME_GITHUB_CONNECTION.md)
- [Agent Execution Runtime MCP Architecture](docs/ARCHITECTURE_DECISIONS.md)

영문 README를 canonical technical document로 유지하며, 각 locale README도 동일한 아키텍처, 용어, Cost-Free 기본 경로를 유지합니다.

**[English](README.md) · [日本語](README.ja.md) · [简体中文](README.zh-CN.md)**

## License

[LICENSE](LICENSE)를 참고하세요.

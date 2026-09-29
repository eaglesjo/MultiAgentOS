# MultiAgentOS

> **Cost-Free Multi-Agent Development Orchestration**

MultiAgentOS는 **VYRELON**을 중심으로 하는 로컬 우선 AI 개발 오케스트레이션 플랫폼입니다.

Cost-free 기본 경로에서는 **별도의 유료 AI API Key가 필요하지 않습니다.** MultiAgentOS는 이미 사용할 수 있는 AI 클라이언트와 GitHub, 로컬 프로젝트를 연결하고 실행 권한은 VYRELON 안에 유지합니다.

## 핵심 구조

- **ChatGPT Web** — 유일한 사용자 진입점
- **ChatGPT Codex Connector** — 원격 GitHub Repository 연결
- **VYRELON MCP / Secure Tunnel** — 로컬 프로젝트 연결
- **Orchestrator** — 전체 멀티 에이전트 협업 조정
- **MultiAgentWorkflow** — Developer → Tester → Reviewer 실행
- Verification / Handoff / Review / Rework
- VYRELON 기반 filesystem / patch / process / Git 실행 권한 제어

## 아키텍처

`text
                         Web Browser
                              |
                              v
                         ChatGPT Web
                              |
                    +---------+---------+
                    |                   |
                    v                   v
       ChatGPT Codex Connector       VYRELON
                    |                MCP / Secure Tunnel
                    v                   |
            GitHub Repository            v
                                  Local Project
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
                     /       |       \\
               Developer   Tester   Reviewer
                              |
                              v
                         Verification
                              |
                              v
                           VYRELON
`

Agent는 의도, 계획, 결과를 제공하지만 filesystem/process/Git 실행 권한을 직접 소유하지 않습니다.

## 멀티 에이전트 워크플로

`text
Request
  |
  v
Orchestrator
  |
  v
MultiAgentWorkflow
  |
  +--> Developer
  +--> Tester
  +--> Reviewer
  +--> 필요한 경우 Rework
  |
  v
Verification
  |
  v
Completed / Failed
`

`Orchestrator.run_workflow()`가 상위 오케스트레이션 진입점이며, `MultiAgentWorkflow`가 단계와 handoff/review/rework semantics를 담당합니다. `MultiAgentRuntime`은 애플리케이션/runtime adapter입니다.

## 연결 모델

### GitHub 경로

`text
ChatGPT Web
    |
    v
ChatGPT Codex Connector
    |
    v
GitHub Repository
`

### 로컬 프로젝트 경로

`text
ChatGPT Web
    |
    v
VYRELON MCP / Secure Tunnel
    |
    v
VYRELON
    |
    v
Local Project
`

VYRELON은 **하나의 MCP Server**만 사용합니다. Secure MCP Tunnel과 `tunnel-client`는 transport/connection infrastructure이며 별도의 MCP Server가 아닙니다.

## Cost-Free 기본 경로

기본 런타임에는 별도의 유료 AI API Key, 별도의 Agent API 구독, MultiAgentOS SaaS 구독이 필요하지 않습니다.

단, 실제 AI 서비스의 사용량 및 플랜 제한은 해당 서비스 정책을 따릅니다.

검증된 기본 기능:

- VYRELON MCP stdio 초기화 및 tool discovery
- filesystem WRITE/READ
- `patch.apply`
- `shell.run`
- local MCP/runtime tests
- runtime health/readiness
- Secure MCP Tunnel readiness

자세한 내용은 [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md)을 참고하세요.

## 설치 및 CLI

`bash
python -m pip install multiagentos

cd your-project
multiagentos init . --component all
multiagentos status .
multiagentos run --path . --objective "run tests" -- python -m unittest discover -s tests -v
multiagentos chat --path . --objective "inspect the current project"
multiagentos mcp serve --path .
`

쓰기와 process 실행이 필요한 경우:

`bash
multiagentos mcp serve \
  --path . \
  --allow-write \
  --allow-process
`

## 문서

- [Getting Started](docs/GETTING_STARTED.md)
- [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md)
- [VYRELON Connection Guide](docs/VYRELON_CONNECTIONS.md)
- [Secure MCP Tunnel Setup](docs/MCP_TUNNEL.md)
- [VYRELON GitHub Connection](docs/VYRELON_GITHUB_CONNECTION.md)
- [VYRELON MCP Architecture](docs/ARCHITECTURE_DECISIONS.md)

영문 README를 canonical technical document로 유지하며, locale README도 동일한 아키텍처와 기술적 의미를 유지합니다.

[English](README.md) · [日本語](README.ja.md) · [简体中文](README.zh-CN.md)

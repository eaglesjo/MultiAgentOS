# MultiAgentOS

> **Cost-Free Multi-Agent Development Orchestration**

MultiAgentOS 是以 **VYRELON** 为核心的 Local-first AI 开发编排平台。

Cost-free 基线**不要求单独的付费 AI API Key**。MultiAgentOS 将可用的 AI 客户端、GitHub 和本地项目连接起来，同时把执行权限保持在 VYRELON 内部。

## 核心结构

- **ChatGPT Web** — 唯一的用户入口
- **ChatGPT Codex Connector** — 远程 GitHub Repository 路径
- **VYRELON MCP / Secure Tunnel** — 本地项目路径
- **Orchestrator** — 多智能体协作的顶层协调
- **MultiAgentWorkflow** — Developer → Tester → Reviewer
- Verification / Handoff / Review / Rework
- VYRELON 控制 filesystem / patch / process / Git 执行权限

## 架构

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

Agent 提供意图、计划和结果，但不直接拥有 filesystem/process/Git 的执行权限。

## 多智能体工作流

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
  +--> 必要时 Rework
  |
  v
Verification
  |
  v
Completed / Failed
`

`Orchestrator.run_workflow()` 是稳定的上层编排入口；`MultiAgentWorkflow` 负责具体的 stage、handoff、review 和 rework 语义。

## 连接模型

### GitHub 路径

`text
ChatGPT Web
    |
    v
ChatGPT Codex Connector
    |
    v
GitHub Repository
`

### 本地项目路径

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

VYRELON **只有一个 MCP Server**。Secure MCP Tunnel 和 `tunnel-client` 是 transport/connection infrastructure，而不是第二个 MCP Server。

## Cost-Free 基线

基本运行时不要求单独的付费 AI API Key、Agent API 订阅或 MultiAgentOS SaaS 订阅。

已验证：

- VYRELON MCP stdio 初始化和 tool discovery
- filesystem WRITE/READ
- `patch.apply`
- `shell.run`
- local MCP/runtime tests
- runtime health/readiness
- Secure MCP Tunnel readiness

详情请参阅 [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md)。

## 安装

`bash
python -m pip install multiagentos

cd your-project
multiagentos init . --component all
multiagentos status .
multiagentos run --path . --objective "run tests" -- python -m unittest discover -s tests -v
multiagentos chat --path . --objective "inspect the current project"
multiagentos mcp serve --path .
`

## 文档

- [Getting Started](docs/GETTING_STARTED.md)
- [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md)
- [VYRELON Connection Guide](docs/VYRELON_CONNECTIONS.md)
- [Secure MCP Tunnel Setup](docs/MCP_TUNNEL.md)
- [VYRELON GitHub Connection](docs/VYRELON_GITHUB_CONNECTION.md)
- [VYRELON MCP Architecture](docs/ARCHITECTURE_DECISIONS.md)

英文 README 是 canonical technical document，各 locale 保持相同的架构和技术含义。

[한국어](README.ko.md) · [日本語](README.ja.md)

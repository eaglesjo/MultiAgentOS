# MultiAgentOS

> **Cost-Free Multi-Agent Development Orchestration**

MultiAgentOSは **VYRELON** を中心とするローカルファーストのAI開発オーケストレーション基盤です。

Cost-freeの基本パスでは、**別途の有料AI API Keyを必要としません**。MultiAgentOSは利用可能なAIクライアント、GitHub、ローカルプロジェクトを連携し、実行権限をVYRELONに保持します。

## 中核構成

- **ChatGPT Web** — 唯一のユーザーエントリーポイント
- **ChatGPT Codex Connector** — リモートGitHub Repositoryへの接続
- **VYRELON MCP / Secure Tunnel** — ローカルプロジェクトへの接続
- **Orchestrator** — マルチエージェント協調の全体調整
- **MultiAgentWorkflow** — Developer → Tester → Reviewer
- Verification / Handoff / Review / Rework
- VYRELONによるfilesystem / patch / process / Git実行権限の制御

## アーキテクチャ

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

Agentは意図・計画・結果を提供しますが、filesystem/process/Gitの実行権限を直接所有しません。

## マルチエージェントワークフロー

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
  +--> 必要に応じて Rework
  |
  v
Verification
  |
  v
Completed / Failed
`

`Orchestrator.run_workflow()` が安定した上位オーケストレーション入口で、`MultiAgentWorkflow` がstage、handoff、review、reworkの具体的な意味を管理します。

## 接続モデル

### GitHub path

`text
ChatGPT Web
    |
    v
ChatGPT Codex Connector
    |
    v
GitHub Repository
`

### Local project path

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

VYRELONには**1つのMCP Server**だけがあります。Secure MCP Tunnelと`tunnel-client`はtransport/connection infrastructureであり、別のMCP Serverではありません。

## Cost-Free baseline

基本ランタイムには別途の有料AI API Key、Agent APIサブスクリプション、MultiAgentOS SaaSサブスクリプションを必要としません。

検証済み:

- VYRELON MCP stdio initialize / tool discovery
- filesystem WRITE/READ
- `patch.apply`
- `shell.run`
- local MCP/runtime tests
- runtime health/readiness
- Secure MCP Tunnel readiness

詳細は [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md) を参照してください。

## インストール

`bash
python -m pip install multiagentos

cd your-project
multiagentos init . --component all
multiagentos status .
multiagentos run --path . --objective "run tests" -- python -m unittest discover -s tests -v
multiagentos chat --path . --objective "inspect the current project"
multiagentos mcp serve --path .
`

## ドキュメント

- [Getting Started](docs/GETTING_STARTED.md)
- [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md)
- [VYRELON Connection Guide](docs/VYRELON_CONNECTIONS.md)
- [Secure MCP Tunnel Setup](docs/MCP_TUNNEL.md)
- [VYRELON GitHub Connection](docs/VYRELON_GITHUB_CONNECTION.md)
- [VYRELON MCP Architecture](docs/ARCHITECTURE_DECISIONS.md)

英語READMEをcanonical technical documentとして維持し、各localeも同じアーキテクチャと技術的意味を保持します。

[한국어](README.ko.md) · [简体中文](README.zh-CN.md)

# MultiAgentOS

> **Cost-Free Multi-Agent Development Orchestration**

MultiAgentOSは **VYRELON** を中心とするローカルファーストのAI開発オーケストレーション基盤です。

Cost-Freeの基本パスでは、**別途の有料AI API Keyを必要としません。** MultiAgentOSは利用可能なAIクライアント、GitHub、ローカルプロジェクトを連携し、実行権限をVYRELONに保持します。

## MultiAgentOSの役割

MultiAgentOSは**AI協調**と**実行権限**を分離します。

- **ChatGPT Web** — 唯一のユーザーエントリーポイント
- **ChatGPT Codex Connector** — リモートGitHub Repositoryへのアクセス
- **VYRELON MCP / Secure Tunnel** — ローカルプロジェクトへの接続
- **Orchestrator** — マルチエージェント協調の全体調整
- **MultiAgentWorkflow** — Developer → Tester → Reviewer
- **VYRELON** — 権限と実行の最終境界

Agentは意図・計画・結果を提供しますが、filesystem、process、patch、Gitの実行権限を直接所有しません。

## アーキテクチャ

```text
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
                     /       |       \
               Developer   Tester   Reviewer
                              |
                              v
                         Verification
                              |
                              v
                           VYRELON
```

### 責任境界

| コンポーネント | 責任 |
| --- | --- |
| **ChatGPT Web** | ユーザーエントリーポイント |
| **ChatGPT Codex Connector** | リモートGitHub Repositoryアクセス |
| **VYRELON MCP / Secure Tunnel** | ローカルプロジェクト接続 |
| **MultiAgentOS** | Agent契約、ルーティング、状態、オーケストレーション |
| **Orchestrator** | 全体の協調調整 |
| **MultiAgentWorkflow** | stage、handoff、review、reworkの意味論 |
| **VYRELON** | 権限と実行の制御 |

## マルチエージェントワークフロー

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
  +--> 必要に応じて Rework
  |
  v
Verification
  |
  v
Completed / Failed
```

`Orchestrator.run_workflow()` が安定した上位オーケストレーション入口です。`MultiAgentWorkflow` が具体的なstage、handoff、review、reworkの意味論を管理し、`MultiAgentRuntime` はアプリケーション/runtime adapterとしてこの境界を利用します。

VYRELONはpermission、filesystem、patch、process、Git、verificationを担当する実行境界です。

## 接続モデル

### リモートGitHub path

```text
ChatGPT Web
    |
    v
ChatGPT Codex Connector
    |
    v
GitHub Repository
```

### ローカルプロジェクト path

```text
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
```

VYRELONには**1つのMCP Server**だけがあります。Secure MCP Tunnelと`tunnel-client`はtransport/connection infrastructureであり、別のMCP Serverではありません。

ローカルVYRELON MCP ServerはOpenAI、ChatGPT、tunnel、または有料AI API Keyなしでも独立して利用できます。

## Cost-Free baseline

基本ランタイムのポイントは明確です。

> **MultiAgentOSのCost-Free基本パスには別途の有料AI API Keyを必要としません。**

さらに、次も基本的には必要ありません。

- 別途のAgent APIサブスクリプション
- MultiAgentOS SaaSサブスクリプション
- Tunnel用の2つ目のMCP Server

ただし、利用するAIサービスのプランおよび使用量制限は適用されます。Cost-FreeはMultiAgentOSのランタイムコスト構造を示すもので、AIサービスの無制限利用を意味しません。

### 検証済みの基本機能

- VYRELON MCP stdio initialize / tool discovery
- filesystem READ / WRITE
- `patch.apply`
- `shell.run`
- local MCP/runtime tests
- runtime health/readiness
- Secure MCP Tunnel readiness

詳細は [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md) を参照してください。

## クイックスタート

### インストール

```bash
python -m pip install multiagentos
```

### プロジェクト初期化

```bash
cd your-project
multiagentos init . --component all
multiagentos status .
```

### ローカルタスク実行

```bash
multiagentos run --path . --objective "run tests" -- python -m unittest discover -s tests -v
```

### Chat Agentセッション開始

```bash
multiagentos chat --path . --objective "inspect the current project"
```

### VYRELON MCP Server起動

```bash
multiagentos mcp serve --path .
```

## 設定

プロジェクト設定は`.multiagentos/`に保存されます。

初期化では次のファイルをインストールできます。

- `components.json` — 選択したcomponent
- `execution.json` — execution Agent/Model選択
- `chat.json` — Chat Agent選択
- `agents.json` — multi-agent catalog
- `state/` および必要なsession/checkpointデータ

Credentialとprovider API keyはプロジェクト設定に保存されません。

## 検証

```bash
python -m unittest discover -s tests -v
```

GitHub ActionsでもリポジトリのCIを検証します。

## ドキュメント

- [Getting Started](docs/GETTING_STARTED.md)
- [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md)
- [VYRELON Connection Guide](docs/VYRELON_CONNECTIONS.md)
- [Secure MCP Tunnel Setup](docs/MCP_TUNNEL.md)
- [VYRELON GitHub Connection](docs/VYRELON_GITHUB_CONNECTION.md)
- [VYRELON MCP Architecture](docs/ARCHITECTURE_DECISIONS.md)

英語READMEをcanonical technical documentとして維持し、各locale READMEも同じアーキテクチャ、用語、Cost-Free基本パスを維持します。

**[한국어](README.ko.md) · [English](README.md) · [简体中文](README.zh-CN.md)**

## License

[LICENSE](LICENSE)を参照してください。

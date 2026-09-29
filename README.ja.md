# MultiAgentOS

**ローカルファースト、GitHubネイティブのAI開発基盤です。**

MultiAgentOSは **VYRELON** の基盤ランタイムであり、マルチエージェント開発オーケストレーターです。リモートGitHubリポジトリと開発者のローカルプロジェクトを明確に分離しながら、対話型AIが実際のプロジェクトで作業できるようにします。

> **2つの接続には、それぞれ異なる役割があります。**
> - **GitHub URL → ChatGPT GitHubアプリ → リモートGitHubリポジトリ**
> - **VYRELON → MCP / Secure MCP Tunnel → ローカルプロジェクト**

## 重要な接続モデル

**GitHub URLはローカルプロジェクトへの接続ではありません。**

GitHub URLまたはrepository nameは、ChatGPT GitHub連携で**どのリモートリポジトリを対象にするか**を指定します。

VYRELONは**ローカル実行境界**です。明示的に許可された場合、filesystem、`patch.apply`、process実行、テスト、MCP tool surfaceなどを提供します。

```text
                  MultiAgentOS
                       |
            +----------+----------+
            |                     |
            v                     v
       GitHub path            Local path
            |                     |
 GitHub URL / repository      VYRELON runtime
            |                     |
 ChatGPT GitHub app       MCP / Secure MCP Tunnel
            |                     |
            v                     v
   Remote GitHub repo         Local project
```

## ChatGPT + GitHub

1. ChatGPTの **Settings → Apps** を開きます。
2. **GitHub**を接続し、GitHub認証を完了します。
3. ChatGPTから検索できるrepositoryへのアクセスを許可します。
4. 新しいChatGPT conversationを開始します。
5. **GitHub URLまたはrepository nameを一度指定**します。
6. 対象repositoryへの作業を依頼します。

例:

> `https://github.com/eaglesjo/MultiAgentOS`を確認し、現在のVYRELON接続モデルとREADMEの改善点を分析してください。

URL/nameの指定は**リモートGitHub repositoryを会話の対象として識別するためのもの**です。これだけでローカルfilesystemへのアクセス権が付与されるわけではありません。

## VYRELON + ローカルプロジェクト

```bash
python -m pip install multiagentos

cd your-project
multiagentos init . --component all
multiagentos status .
```

ローカルMCPサーバー:

```bash
multiagentos mcp serve --path /absolute/path/to/project
```

writeとprocess capabilityが必要な場合:

```bash
multiagentos mcp serve \
  --path /absolute/path/to/project \
  --allow-write \
  --allow-process
```

## ChatGPT/Codex + ローカルVYRELON

```text
ChatGPT / Codex
       |
Secure MCP Tunnel
       |
 tunnel-client
       |
VYRELON MCP Server
       |
Local Project
```

Secure MCP Tunnelは新しいMCPサーバーではありません。同じVYRELON MCP Serverへ接続するためのtransport/connection infrastructureです。

## Cost-free baseline

MultiAgentOSの主要なローカル開発パスでは、有料AI provider API keyを必須としません。

VYRELONはAI providerとは独立してfilesystem READ/WRITE、patch application、process/test execution、local MCP runtimeを提供できます。

詳細は [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md) を参照してください。

## Validation

```bash
python -m unittest discover -s tests -v
```

## Documentation

- [English README](README.md)
- [한국어 README](README.ko.md)
- [Getting Started](docs/GETTING_STARTED.md)
- [VYRELON Connection Guide](docs/VYRELON_CONNECTIONS.md)
- [Secure MCP Tunnel Setup](docs/MCP_TUNNEL.md)

## Localization

英語版READMEをcanonical documentとして維持します。各localeでは、文章だけでなく技術用語と接続モデルの意味を維持します。

VYRELON、MultiAgentOS、GitHub、MCP、Secure MCP Tunnel、`patch.apply`、filesystem、process、execution policy、permission boundary、Chat Agent、Model、Agent、Runtimeなどの用語は技術的意味を変更しません。

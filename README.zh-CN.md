# MultiAgentOS

**一个 Local-first、GitHub-native 的 AI 软件开发基础平台。**

MultiAgentOS 是 **VYRELON** 的基础运行时和多智能体开发编排器。它让对话式 AI 能够参与真实项目，同时明确区分远程 GitHub 仓库与开发者本地项目。

> **两条连接路径承担不同职责。**
> - **GitHub URL → ChatGPT GitHub 应用 → 远程 GitHub 仓库**
> - **VYRELON → MCP / Secure MCP Tunnel → 本地项目**

## 最重要的连接模型

**GitHub URL 不是本地项目连接。**

GitHub URL 或 repository name 用于告诉 ChatGPT GitHub 集成：**当前对话要操作哪个远程仓库**。

VYRELON 则是**本地执行边界**。在明确授权后，它可以提供 filesystem、`patch.apply`、process 执行、测试和 MCP tool surface。

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

1. 在 ChatGPT 中打开 **Settings → Apps**。
2. 连接 **GitHub** 并完成 GitHub 授权。
3. 授权 ChatGPT 搜索所需的 repository。
4. 创建一个新的 ChatGPT conversation。
5. **指定一次 GitHub URL 或 repository name**。
6. 提出针对该 repository 的开发任务。

例如：

> 检查 `https://github.com/eaglesjo/MultiAgentOS`，解释当前 VYRELON 连接模型，并分析第一版 README 需要改进的部分。

指定 URL/name 的作用是**确定当前对话对应的远程 GitHub repository**。这不会自动授予 ChatGPT 本地 filesystem 访问权限。

## VYRELON + 本地项目

```bash
python -m pip install multiagentos

cd your-project
multiagentos init . --component all
multiagentos status .
```

启动本地 MCP：

```bash
multiagentos mcp serve --path /absolute/path/to/project
```

需要写入和 process capability 时：

```bash
multiagentos mcp serve \
  --path /absolute/path/to/project \
  --allow-write \
  --allow-process
```

## ChatGPT/Codex + 本地 VYRELON

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

Secure MCP Tunnel 不是另一个 MCP Server，而是让远程客户端连接同一个 VYRELON MCP Server 的 transport/connection infrastructure。

## Cost-free baseline

MultiAgentOS 的核心本地开发路径不要求付费 AI provider API key。

VYRELON 可以独立于 AI provider 提供 filesystem READ/WRITE、patch application、process/test execution 和 local MCP runtime。

详细信息请参阅 [Cost-Free Development Baseline](docs/COSTFREE_DEVELOPMENT.md)。

## Validation

```bash
python -m unittest discover -s tests -v
```

## Documentation

- [English README](README.md)
- [한국어 README](README.ko.md)
- [日本語 README](README.ja.md)
- [Getting Started](docs/GETTING_STARTED.md)
- [VYRELON Connection Guide](docs/VYRELON_CONNECTIONS.md)
- [Secure MCP Tunnel Setup](docs/MCP_TUNNEL.md)

## Localization

英文 README 是 canonical document。各 locale 应保持相同的技术含义和连接模型。

VYRELON、MultiAgentOS、GitHub、MCP、Secure MCP Tunnel、`patch.apply`、filesystem、process、execution policy、permission boundary、Chat Agent、Model、Agent、Runtime 等术语不应改变其技术含义。

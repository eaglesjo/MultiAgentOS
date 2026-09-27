# MultiAgentOS

MultiAgentOS is the integration base for **VYRELON**, a local-first, GitHub-native AI development runtime with optional Multi-Agent orchestration.

VYRELON absorbs and generalizes the strongest capabilities of three source systems:

- `free-claude-code` — provider/model/protocol/harness, streaming, tool calling and fallback
- `luna-chat-coder` — repository continuity, recovery, validation and evidence
- `chatgpt-local-coder` — local filesystem, shell/process, Git, patch, permissions, checkpoints and MCP

Multi-Agent is an **extension layer** on top of VYRELON. It does not define the core runtime.

## What VYRELON is

The target runtime is:

```text
                              VYRELON
                                 │
       ┌─────────────────────────┼─────────────────────────┐
       │                         │                         │
   AI Runtime              Local Runtime           Repository Runtime
       │                         │                         │
 Provider / Model          Filesystem / Shell       Git / GitHub
 Protocol / Streaming      Process / Patch          Recovery / CI
 Tool Calling / Reasoning  Permission / Path        Checkpoint / Evidence
 Fallback
       │                         │                         │
       └─────────────────────────┼─────────────────────────┘
                                 │
                           Session / Tool
                                 │
                         Optional Multi-Agent
                    Planner / Coder / Reviewer
```

The runtime is designed so that a project can use VYRELON alone or enable Multi-Agent orchestration when needed.

## ChatGPT Web as the VYRELON entry point

A primary VYRELON usage model is **ChatGPT Web controlling a development environment**.

There are two complementary ChatGPT-to-project paths:

1. **ChatGPT Web → local machine through MCP**
2. **ChatGPT Web → GitHub through the GitHub app/connection**

These paths are intentionally separate. Local machine access is a tool-execution path; GitHub access is a repository-data and repository-operation path.

### 1. ChatGPT Web → Local machine through MCP Tunnel

ChatGPT cannot directly connect to a local MCP server. A local VYRELON MCP server therefore needs a secure remote transport such as an OpenAI Secure MCP Tunnel. The tunnel connects ChatGPT Web to the MCP server without requiring the local development machine to expose its MCP port publicly.

The intended flow is:

```text
┌──────────────────┐
│   ChatGPT Web    │
│  browser chat    │
└────────┬─────────┘
         │ MCP over HTTPS
         ▼
┌──────────────────┐
│  Secure MCP      │
│     Tunnel       │
└────────┬─────────┘
         │ localhost
         ▼
┌──────────────────┐
│ VYRELON MCP      │
│ Local Runtime    │
└────────┬─────────┘
         │
    ┌────┼──────────────┐
    ▼    ▼              ▼
 Files  Shell/Process   Git/Patch
```

This is the architecture being absorbed from `chatgpt-local-coder`. Its MCP server exposes structured local tools such as filesystem operations, shell commands, Git operations and patch application.

#### Local MCP security model

The local endpoint must be treated as a privileged development interface:

- bind the MCP server to loopback where possible;
- expose only the MCP port through the tunnel;
- never expose a local administration port through the tunnel;
- use an MCP authentication token when the transport supports path/token authentication;
- keep tunnel credentials separate from repository credentials;
- enforce VYRELON filesystem/path policy before executing a tool;
- enforce explicit write/process/Git permissions;
- record mutation and execution evidence;
- never persist raw secrets in WorkUnit/session state.

The MCP tunnel is transport. **VYRELON Local Tool Runtime remains the security and execution boundary.**

> ChatGPT's current MCP availability and write/modify capabilities depend on plan and workspace configuration. OpenAI documents full MCP support as rolling out for supported ChatGPT Business and Enterprise/Edu workspaces; availability and UI can change.

### Local MCP setup pattern

The concrete local setup follows this sequence:

1. Install/start the VYRELON MCP server on the development machine.
2. Bind it to localhost.
3. Configure the project/workspace root.
4. Generate an MCP authentication token.
5. Start the secure MCP tunnel.
6. Register the MCP endpoint as a ChatGPT custom MCP app/connector.
7. Enable that app in the ChatGPT conversation.
8. Ask ChatGPT to inspect, edit, test or operate the local project through VYRELON tools.

For example:

```text
ChatGPT:
  "Read the project README, run the tests, fix the failing test,
   show the diff, and stop before committing."

          ↓

MCP Tool Calls:
  filesystem.read
  shell.run
  patch.apply
  git.diff

          ↓

VYRELON Policy
  path check
  permission check
  execution
  evidence

          ↓

ChatGPT receives structured results
```

The exact tunnel command is environment-specific and should be kept in the MCP runtime documentation rather than hard-coded into the core runtime.

### 2. ChatGPT Web → GitHub

ChatGPT can also connect directly to GitHub through its supported GitHub app/connection. The connection allows ChatGPT to retrieve permitted repository content such as source code, README files and documentation on demand.

The intended repository flow is:

```text
ChatGPT Web
     │
     │ GitHub connection
     ▼
GitHub
     │
 ┌───┼───────────────┐
 ▼   ▼               ▼
Code README       Issues / repository data
     │
     ▼
VYRELON reasoning / planning
     │
     ├── local MCP → local workspace
     │
     └── GitHub runtime / approved repository actions
```

For standard GitHub access, connect the GitHub app in ChatGPT and grant it access to the repositories that ChatGPT should be allowed to read. Private or newly created repositories may require the GitHub app installation/configuration to explicitly include that repository.

For **write/modify workflows**, use an explicitly authorized GitHub runtime or custom MCP app with the required permissions. Do not assume that the standard GitHub connection provides arbitrary repository writes.

This distinction is important:

| Path | Primary purpose |
|---|---|
| ChatGPT → GitHub connection | Search/read/cite authorized repository content |
| ChatGPT → VYRELON MCP | Execute local tools on the development machine |
| VYRELON GitHub Runtime | Controlled repository mutations and GitHub lifecycle |
| ChatGPT → VYRELON + both | Full local + repository development workflow |

## Current VYRELON runtime

Implemented foundation:

- provider-neutral WorkUnit, Agent, Model, Runtime and Profile contracts
- Harness / Session / Tool / ToolRequest / ToolResult contracts
- normalized RuntimeEvent and ProtocolAdapter contracts
- deterministic model routing
- generic CLI and HTTP model adapters
- model-backed agent execution
- declarative provider/model configuration
- environment-backed credential validation without storing secrets
- policy-controlled local process and GitHub runtimes
- ProjectProfile and AgentProfile resolution
- persistent WorkUnit lifecycle
- GitHub runtime facade
- Local Tool Runtime foundation:
  - path security
  - filesystem read/write/list/create/delete
  - persistent working-directory shell state
  - environment state
  - unified patch check/apply
  - Git status/diff/log/add/restore/stash/branch/commit/push/pull
  - explicit local write/process/Git policy
- GitHub Actions CI validation

## CLI

```bash
multiagentos detect .
multiagentos profile .
multiagentos init .
multiagentos providers list .
multiagentos providers validate .
multiagentos models run . --model <model-id> --objective "..."
multiagentos github probe eaglesjo/MultiAgentOS
```

Optional provider/model definitions live at:

```text
.multiagentos/providers.json
```

Provider credentials are referenced through environment variables. VYRELON never writes credential values to project configuration or WorkUnit state.

## Local Tool Runtime

The first runtime layer is intentionally independent of any AI provider.

```text
Agent / Harness
      │
      ▼
Tool Request
      │
      ▼
Permission + Path Security
      │
      ▼
Local Tool Runtime
 ├── Filesystem
 ├── Shell / Process
 ├── Patch
 └── Git
      │
      ▼
Tool Result / Evidence
```

The local runtime can be used directly by Python integrations and will later be exposed through the VYRELON MCP runtime.

Example:

```python
from pathlib import Path

from runtime.vyrelon import VYRELONRuntime

runtime = VYRELONRuntime()
root = Path("/path/to/project")

filesystem = runtime.local_filesystem(root)
shell = runtime.local_shell(root)
patch = runtime.local_patch(root)

print(filesystem.read_text("README.md"))
print(shell.run("python -m unittest discover -s tests -v").returncode)
```

## Development sequence

VYRELON implementation proceeds in this order:

1. **Local Tool Runtime**
   - Filesystem
   - Shell / Process
   - Git
   - Patch
   - Permission / Path Security

2. **AI Runtime**
   - Provider / Model
   - Protocol
   - Streaming / Event
   - Tool Calling
   - Reasoning
   - Fallback

3. **Repository Runtime**
   - GitHub
   - Recovery
   - Checkpoint
   - Evidence
   - CI / Actions

4. **MCP Runtime**
   - MCP Upstream
   - Session
   - Proxy
   - OAuth
   - Tool Profile

5. **Validation Runtime**
   - Post-edit hooks
   - Test
   - Lint
   - Type Check
   - Validation Evidence

6. **Multi-Agent Runtime**
   - Planner
   - Delegation
   - Coder
   - Reviewer
   - Handoff
   - WorkUnit
   - State / Recovery

Only after these six layers are complete will VYRELON be evaluated for IDE-specific plugin/extension integrations.

## Validation

Run the local test suite with:

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs the repository validation suite for pull requests and pushes.

## Security boundary

VYRELON treats local development access as privileged execution.

```text
ChatGPT / Agent
      │
      ▼
MCP / Runtime Tool
      │
      ▼
Path + Permission Policy
      │
      ├── allow
      └── deny
      │
      ▼
Local Process / Filesystem / Git
      │
      ▼
Audit / Evidence
```

Never expose an unrestricted local shell or filesystem server directly to the public internet. Use a controlled MCP transport and VYRELON policy boundary.

## Source architecture

Detailed capability mapping is maintained in:

- `docs/architecture/VYRELON_SOURCE_INVENTORY.md`
- `docs/architecture/VYRELON_TARGET_ARCHITECTURE.md`

The source projects are reference implementations and capability sources. VYRELON absorbs behavior through provider-neutral contracts and runtime boundaries rather than copying source repositories wholesale.

## References

- ChatGPT Developer Mode and MCP apps: https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt
- Connecting GitHub to ChatGPT: https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt
- OpenAI Apps SDK: https://help.openai.com/en/articles/12515353-build-with-the-apps-sdk

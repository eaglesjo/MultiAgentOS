# Cost-Free Development Baseline

## Purpose

MultiAgentOS is designed so that a project can be developed without requiring a paid AI API key.

The baseline architecture keeps the MCP runtime local:

```
Local AI client
      |
      v
127.0.0.1:8000/mcp
      |
      v
MultiAgentOS / Agent Execution Runtime
      |
      +-- GitHub
      +-- local filesystem
      +-- patch
      +-- process/test
```

Paid API providers are optional. A provider may be added later without changing the project workspace or Agent Execution Runtime permission boundary.

## COSTFREE-001

### Baseline acceptance test

A fresh environment must be able to reach the following workflow without requiring an OpenAI, Anthropic, Gemini, or other paid model API key:

```
Install MultiAgentOS
    |
    v
multiagentos init .
    |
    v
Agent Execution Runtime MCP
    |
    v
AI client
    |
    +-- READ project file
    +-- PATCH project file
    +-- TEST project
```

The test is about **AI API cost**, not about whether an AI service account or product subscription is free.

### Required capabilities

| Capability | Required |
|---|---|
| Project workspace | Yes |
| GitHub integration | Yes |
| Local filesystem READ | Yes |
| Local filesystem WRITE/PATCH | Yes |
| Process/test execution | Yes |
| Paid AI API key | No |
| Optional paid model/provider | Allowed |

## Verified Agent Execution Runtime client path

A real Codex session successfully discovered the Agent Execution Runtime MCP tool catalog and invoked the local runtime.

### Filesystem WRITE/READ

The AI client created and read back:

```
/Volumes/DevFiles/GitHubProject/MultiAgentOS/COSTFREE_TEST.md
```

Tools actually invoked:

```
mcp__agent-execution-runtime__filesystem_write
mcp__agent-execution-runtime__filesystem_read
```

The returned file content matched the requested COSTFREE-001 test content. The file was not created through shell commands, Python, `cat`, or `echo`.

**Result: PASS**

### Shell/process execution

The AI client discovered:

```
mcp__agent-execution-runtime__shell_run
```

and executed `pwd` through that MCP tool.

Observed result:

```
returncode: 0
stdout: /Volumes/DevFiles/GitHubProject/MultiAgentOS
stderr: ""
```

**Result: PASS**

### Patch

The AI client performed a real end-to-end `patch.apply` operation through the Agent Execution Runtime.

Test sequence:

1. Created `Agent Execution Runtime_PATCH_TEST.md` with the content `before`.
2. Applied a unified Git patch through `mcp__agent-execution-runtime__patch_apply`.
3. Read the file back through `mcp__agent-execution-runtime__filesystem_read`.

Observed result:

```
patch.apply returncode: 0
patch.apply stderr: ""
filesystem.read result:
after
```

**Result: PASS**

The implementation intentionally treats `patch.apply` as a `filesystem.write` capability. Although the local implementation invokes Git internally, that subprocess is an implementation detail and does not require the separately exposed `process` capability.

### Code-level runtime tests

The local MCP/runtime test suite was executed after the patch-runtime change:

```
python3 -m unittest tests.test_mcp_server tests.test_local_tool_runtime

Ran 10 tests
OK
```

**Result: PASS (10/10)**

## ChatGPT Web, ChatGPT Mobile, and Secure MCP Tunnel

### Verified client capability

The current development environment has verified two distinct ChatGPT client boundaries:

| Client | GitHub | Local MCP | Result |
| --- | --- | --- | --- |
| ChatGPT Web | Yes | Yes | **Verified** |
| ChatGPT Mobile | Yes | No | **Verified** |

This is a client-capability observation for the current setup. It should not be generalized to every ChatGPT account, plan, or future client configuration.

ChatGPT Web therefore provides the complete user-facing path in the verified setup:

```text
ChatGPT Web
   +--> GitHub Connector --> GitHub Repository
   |
   +--> Local MCP --> 127.0.0.1:8000/mcp --> Local Project
```

ChatGPT Mobile currently uses the GitHub path only:

```text
ChatGPT Mobile
   |
   v
GitHub Connector
   |
   v
GitHub Repository
```

### Secure MCP Tunnel

Secure MCP Tunnel is an optional integration for supported external clients that need to reach a private local MCP server. It is not part of the cost-free local MCP acceptance path.

The current MultiAgentOS local runtime uses:

- the Agent Execution Runtime as the local MCP server
- `tunnel-client` as the outbound tunnel client
- the `agent-execution-runtime-local` tunnel runtime
- an absolute MultiAgentOS MCP command under the project's `.venv`

The tunnel/runtime layer is therefore independent of the AI model provider.

### Hosted remote MCP client boundary

OpenAI's current documentation states that **full MCP support, including modify/write actions, is available for ChatGPT Business and Enterprise/Edu**, while Pro users can connect custom MCPs with read/fetch permissions in developer mode. The documentation also states that ChatGPT connects to remote MCP servers and that a private/developer-machine server can use Secure MCP Tunnel. citeturn0search10

Therefore:

> A healthy `agent-execution-runtime-local` tunnel does not by itself prove that the current ChatGPT account can perform local filesystem writes.

For the current Free account, hosted remote custom-MCP write validation through the Secure MCP Tunnel is **not an executable acceptance test** under the documented plan boundary. This does not affect the verified direct local MCP path from ChatGPT Web. It is a ChatGPT product/plan boundary for the optional hosted tunnel path, not a MultiAgentOS local-runtime failure.

### Optional remote verification state

| Layer | State |
|---|---|
| Agent Execution Runtime local MCP | **PASS** |
| Secure MCP Tunnel | **READY** |
| Remote MCP architecture | **SUPPORTED** |
| ChatGPT Web local MCP in the verified setup | **PASS** |
| ChatGPT Web remote hosted-tunnel write verification | **OPTIONAL / NOT REQUIRED FOR LOCAL BASELINE** |

When a workspace with full MCP/developer-mode write access is available, the remaining validation is:

```
ChatGPT Web
   |
   v
Custom MCP app
   |
   v
Secure MCP Tunnel
   |
   v
Agent Execution Runtime
   |
   +-- filesystem.read
   +-- filesystem.write
   +-- patch.apply
   +-- shell.run
```

OpenAI's documented setup path is to create a custom app in Developer Mode, configure the MCP endpoint, scan its tools, and test the exposed actions; write/modify actions may require confirmation. citeturn0search10

## Verification states

### Verified

- Agent Execution Runtime MCP stdio initialization and tool discovery.
- Local runtime health/readiness.
- Automatic runtime recovery through launchd.
- GitHub-connected development path.
- AI-client Agent Execution Runtime `filesystem.write` and `filesystem.read`.
- AI-client Agent Execution Runtime `shell_run`.
- AI-client Agent Execution Runtime `patch.apply` with filesystem readback.
- End-to-end COSTFREE-001 filesystem WRITE/READ path.
- End-to-end COSTFREE-001 PATCH path.
- Local MCP/runtime tests: 10/10 PASS.
- Secure MCP Tunnel remains available as an optional remote integration path.

### Deferred / plan-gated

- ChatGPT Web remote hosted Secure MCP Tunnel tool calls.
- ChatGPT Mobile local MCP access (not available in the verified setup).

## Design rule

Do not make an OpenAI API key a prerequisite for installing or operating MultiAgentOS.

The system may support:

- ChatGPT Web
- Codex
- Gemini
- Claude
- local LLMs
- other MCP-capable clients
- paid API providers

as interchangeable AI-side choices while keeping the project workspace and Agent Execution Runtime runtime stable.

## Verification record

- Patch-runtime fix commit: `49711818b5dbb267ee2d5b283c3a0da85ee101c8`
- Runtime test result: `10/10 PASS`
- Agent Execution Runtime `patch.apply`: `returncode 0`, empty stderr
- Agent Execution Runtime readback: `after`
- Secure MCP Tunnel: **READY**
- Paid AI API key required for these verified runtime capabilities: **No**
- ChatGPT Web hosted remote MCP/write verification: **plan-gated; not required for the core COSTFREE-001 runtime acceptance**

Keep AI-client invocations minimal: once a capability is verified, reuse the evidence rather than spending additional client quota on redundant smoke tests.

# Cost-Free Development Baseline

## Purpose

MultiAgentOS is designed so that a project can be developed without requiring a paid AI API key.

The baseline architecture separates the development workspace from the AI provider:

```
AI client/provider
      |
      v
MultiAgentOS / VYRELON
      |
      +-- GitHub
      +-- local filesystem
      +-- patch
      +-- process/test
```

Paid API providers are optional. A provider may be added later without changing the project workspace or VYRELON permission boundary.

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
VYRELON MCP
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

## Verified VYRELON client path

A real Codex session successfully discovered the VYRELON MCP tool catalog and invoked the local runtime.

### Filesystem WRITE/READ

The AI client created and read back:

```
/Volumes/DevFiles/GitHubProject/MultiAgentOS/COSTFREE_TEST.md
```

Tools actually invoked:

```
mcp__vyrelon__filesystem_write
mcp__vyrelon__filesystem_read
```

The returned file content matched the requested COSTFREE-001 test content. The file was not created through shell commands, Python, `cat`, or `echo`.

**Result: PASS**

### Shell/process execution

The AI client discovered:

```
mcp__vyrelon__shell_run
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

The AI client performed a real end-to-end `patch.apply` operation through VYRELON.

Test sequence:

1. Created `VYRELON_PATCH_TEST.md` with the content `before`.
2. Applied a unified Git patch through `mcp__vyrelon__patch_apply`.
3. Read the file back through `mcp__vyrelon__filesystem_read`.

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

## ChatGPT Web and Secure MCP Tunnel

OpenAI documents that a private/local MCP server can be connected to supported OpenAI products through Secure MCP Tunnel without exposing the local server directly to the public Internet. citeturn0search10

The current MultiAgentOS local runtime uses:

- VYRELON as the local MCP server
- `tunnel-client` as the outbound tunnel client
- the `vyrelon-local` tunnel runtime
- an absolute MultiAgentOS MCP command under the project's `.venv`

The tunnel/runtime layer is therefore independent of the AI model provider.

### Current ChatGPT Web plan boundary

OpenAI's current documentation states that **full MCP support, including modify/write actions, is available for ChatGPT Business and Enterprise/Edu**, while Pro users can connect custom MCPs with read/fetch permissions in developer mode. The documentation also states that ChatGPT connects to remote MCP servers and that a private/developer-machine server can use Secure MCP Tunnel. citeturn0search10

Therefore:

> A healthy `vyrelon-local` tunnel does not by itself prove that the current ChatGPT account can perform local filesystem writes.

For the current Free account, ChatGPT Web write-capable custom MCP validation is **not an executable acceptance test** under the documented plan boundary. This is a ChatGPT product/plan limitation, not a VYRELON runtime failure. The tunnel and local MCP implementation remain valid integration targets.

### ChatGPT Web verification state

| Layer | State |
|---|---|
| VYRELON local MCP | **PASS** |
| Secure MCP Tunnel | **READY** |
| Remote MCP architecture | **SUPPORTED** |
| ChatGPT Web full MCP/write on current Free account | **BLOCKED BY PLAN** |
| ChatGPT Web write verification | **DEFERRED** |

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
VYRELON
   |
   +-- filesystem.read
   +-- filesystem.write
   +-- patch.apply
   +-- shell.run
```

OpenAI's documented setup path is to create a custom app in Developer Mode, configure the MCP endpoint, scan its tools, and test the exposed actions; write/modify actions may require confirmation. citeturn0search10

## Verification states

### Verified

- VYRELON MCP stdio initialization and tool discovery.
- Local runtime health/readiness.
- Automatic runtime recovery through launchd.
- GitHub-connected development path.
- AI-client VYRELON `filesystem.write` and `filesystem.read`.
- AI-client VYRELON `shell_run`.
- AI-client VYRELON `patch.apply` with filesystem readback.
- End-to-end COSTFREE-001 filesystem WRITE/READ path.
- End-to-end COSTFREE-001 PATCH path.
- Local MCP/runtime tests: 10/10 PASS.
- Secure MCP Tunnel runtime is ready for remote MCP integration.

### Deferred / plan-gated

- ChatGPT Web custom MCP discovery against `vyrelon-local`.
- ChatGPT Web local filesystem WRITE through VYRELON.

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

as interchangeable AI-side choices while keeping the project workspace and VYRELON runtime stable.

## Verification record

- Patch-runtime fix commit: `49711818b5dbb267ee2d5b283c3a0da85ee101c8`
- Runtime test result: `10/10 PASS`
- VYRELON `patch.apply`: `returncode 0`, empty stderr
- VYRELON readback: `after`
- Secure MCP Tunnel: **READY**
- Paid AI API key required for these verified runtime capabilities: **No**
- ChatGPT Web full MCP/write verification: **plan-gated; not required for the core COSTFREE-001 runtime acceptance**

Keep AI-client invocations minimal: once a capability is verified, reuse the evidence rather than spending additional client quota on redundant smoke tests.

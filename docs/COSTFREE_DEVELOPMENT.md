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

The `patch.apply` MCP tool is exposed by VYRELON and was discovered by the AI client.

**Actual patch application: PENDING**

## ChatGPT Web and Secure MCP Tunnel

OpenAI Secure MCP Tunnel can connect a private/local MCP server to supported OpenAI products without exposing the local MCP server to the public Internet.

The current MultiAgentOS local runtime uses:

- VYRELON as the local MCP server
- `tunnel-client` as the outbound tunnel client
- the `vyrelon-local` tunnel runtime
- an absolute MultiAgentOS MCP command under the project's `.venv`

The tunnel/runtime layer is therefore independent of the AI model provider.

### ChatGPT Web limitation

ChatGPT developer-mode MCP access is controlled separately from Platform tunnel permissions. A tunnel can be healthy and ready while the current ChatGPT account/workspace cannot create or use a write-capable custom MCP app.

Therefore:

> A healthy `vyrelon-local` runtime does not by itself prove that this ChatGPT session can write to the local filesystem.

The ChatGPT Web path must be treated as an integration target, not as the only implementation of COSTFREE-001.

## Verification states

### Verified

- VYRELON MCP stdio initialization and tool discovery.
- Local runtime health/readiness.
- Automatic runtime recovery through launchd.
- GitHub-connected development path.
- AI-client VYRELON `filesystem.write` and `filesystem.read`.
- AI-client VYRELON `shell_run`.
- End-to-end COSTFREE-001 filesystem WRITE/READ path.

### Pending

- Actual VYRELON `patch.apply` application and verification.
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

## Next verification step

The next concrete runtime test is an actual `patch.apply` operation through VYRELON, followed by a VYRELON `filesystem.read` verification and a VYRELON `shell_run` test.

Keep AI-client invocations minimal: once a capability is verified, reuse the evidence rather than spending additional client quota on redundant smoke tests.

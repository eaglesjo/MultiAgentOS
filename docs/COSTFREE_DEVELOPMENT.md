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

### Pending

- ChatGPT Web custom MCP discovery against `vyrelon-local`.
- ChatGPT Web local filesystem WRITE through VYRELON.
- End-to-end COSTFREE-001 using a non-paid-API development client.

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

Use a client that can actually discover the VYRELON MCP tool catalog and invoke:

1. `filesystem.write`
2. `filesystem.read`
3. `patch.apply`
4. process/test tooling

The first concrete artifact should be `COSTFREE_TEST.md` created by the AI client through VYRELON. The file must not be created manually, because manual creation would bypass the WRITE test.

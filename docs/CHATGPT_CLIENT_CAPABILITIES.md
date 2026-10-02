# ChatGPT Client Capability Matrix

## Purpose

This document records the ChatGPT client boundary verified during the MultiAgentOS 0.4.2 local MCP validation.

It is a compatibility record for the verified development environment. It is not a universal guarantee for every ChatGPT account, plan, client build, or future product configuration.

## Verified matrix

| Client | GitHub repository | Local MultiAgentOS MCP | Verified use |
| --- | --- | --- | --- |
| **ChatGPT Web** | Yes | Yes | Full development workflow |
| **ChatGPT Mobile App** | Yes | No | GitHub-only workflow |
| **ChatGPT Desktop** | Not evaluated | Not evaluated | Outside current release scope |

## ChatGPT Web

In the verified setup, ChatGPT Web can use both sides of the MultiAgentOS development boundary:

```text
ChatGPT Web
   |
   +--> GitHub connection --> GitHub Repository
   |
   +--> Local MCP --> 127.0.0.1:8000/mcp --> Local Project
```

This means the browser client can work with the durable remote repository and the local working tree through the corresponding connections.

The local MCP path does not require a paid AI API key or Secure MCP Tunnel.

## ChatGPT Mobile App

In the verified setup, the mobile client can use the GitHub connection:

```text
ChatGPT Mobile
   |
   v
GitHub connection
   |
   v
GitHub Repository
```

Local MCP access is not available in the verified mobile setup.

Therefore, a task that requires direct access to the developer's local working tree must be performed from a client that exposes the local MCP connection, such as the verified ChatGPT Web setup.

## Cost-free boundary

The client matrix does not change the MultiAgentOS cost-free architecture:

- Local MCP remains the primary local execution path.
- No paid OpenAI API key is required for the local MCP service.
- Secure MCP Tunnel remains optional for remote clients that need to reach a private local MCP server.
- GitHub access and local filesystem access are separate capabilities.

## macOS local service

The verified local MCP service is managed by macOS `launchd`:

```text
macOS login/reboot
      |
      v
launchd
      |
      v
MultiAgentOS MCP
      |
      v
127.0.0.1:8000/mcp
```

The 0.4.2 validation confirmed that the service survives reboot and returns an MCP protocol response when accessed locally.

## Maintenance rule

When client capabilities change, update this document and the corresponding README/connection guides before changing the core MultiAgentOS MCP architecture.

Do not introduce Secure MCP Tunnel or an AI API key into the default local workflow merely to compensate for a client-specific limitation.

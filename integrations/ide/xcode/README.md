# Agent Execution Runtime Xcode Adapter

This directory contains the native XcodeKit adapter for Agent Execution Runtime.

The adapter is intentionally thin:
- XcodeKit owns the editor integration.
- Agent Execution Runtime owns AI execution, local tools, Git, MCP, validation, and multi-agent orchestration.
- IDE-originated information is normalized as Agent Execution Runtime IDE events.
- Agent Execution Runtime-originated editor operations are normalized as IDE commands.
- The core Python runtime has no dependency on XcodeKit.

The initial adapter uses a loopback-only Agent Execution Runtime bridge:
- default endpoint: `http://127.0.0.1:8787`
- IDE -> Agent Execution Runtime: `POST /v1/ide/event`
- Agent Execution Runtime -> IDE: `POST /v1/ide/command`

## Build

Open `AgentExecutionRuntimeXcode.xcodeproj` in Xcode and build the Source Editor Extension target.

The project is a native Swift/XcodeKit adapter scaffold. Distribution/signing and App Store or other packaging decisions are intentionally deferred until the bridge and integration tests are hardened.

## Security

The adapter must only communicate with an explicitly configured local Agent Execution Runtime endpoint. Do not expose the bridge directly to the public network.

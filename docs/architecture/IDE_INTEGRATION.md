# Agent Execution Runtime IDE Integration Architecture

Agent Execution Runtime treats IDE support as an adapter layer above the six completed core runtimes. The Agent Execution Runtime core never imports an IDE SDK.

## Supported targets

| IDE | Native integration mechanism | Adapter technology |
|---|---|---|
| Xcode | XcodeKit Source Editor Extension | Swift / Xcode project |
| VS Code | VS Code Extension API | TypeScript |
| Android Studio | IntelliJ Platform Plugin API | Kotlin / JVM |

XcodeKit source editor extensions can read and modify source contents and the current selection. VS Code provides commands, editor/workspace APIs and optional Webviews. Android Studio is an IntelliJ Platform product and supports plugins through the IntelliJ Platform SDK. See Apple XcodeKit, VS Code Extension API, and JetBrains Android Studio plugin documentation for the current platform contracts.

## Boundary

Agent Execution Runtime Core
  |
  +-- IDE Adapter Contract
       |
       +-- Xcode adapter (Swift / XcodeKit)
       +-- VS Code adapter (TypeScript / VS Code API)
       +-- Android Studio adapter (Kotlin/JVM / IntelliJ API)

The adapters translate native IDE state and actions into:

- IDEContext
- IDECommand
- IDECommandResult

The core therefore remains independent of XcodeKit, the VS Code API, and IntelliJ classes.

## Adapter responsibilities

Minimum capabilities:

- project/workspace root
- active file
- current selection
- language/file metadata
- context retrieval
- explicit command execution
- result/error reporting

Optional capabilities are advertised through capabilities().

An adapter must not silently broaden permissions. File writes, shell execution, network access, Git operations, MCP tools, and multi-agent execution remain governed by Agent Execution Runtime's existing security and runtime boundaries.

## Connection modes

### In-process IDE extension

Preferred for editor-aware operations:

- Xcode: Source Editor Extension
- VS Code: extension host
- Android Studio: IntelliJ Platform plugin

The extension delegates persistent development work to Agent Execution Runtime rather than reimplementing the Agent Execution Runtime runtimes.

### Local bridge

For richer sessions an adapter may communicate with a local Agent Execution Runtime process over a localhost-only transport.

IDE plugin
  |
  | localhost bridge
  v
Agent Execution Runtime Runtime
  +-- Local Tool Runtime
  +-- AI Runtime
  +-- Repository Runtime
  +-- MCP Runtime
  +-- Validation Runtime
  +-- Multi-Agent Runtime

Authentication and authorization must be explicit. An IDE adapter must not expose a public network listener just to connect to Agent Execution Runtime.

## IDE-specific implementation

### Xcode

Use XcodeKit for source-editor commands and editor context. XcodeKit supports reading and modifying source contents and the current selection.

Build/test/device workflows stay in Agent Execution Runtime Local Tool Runtime and, where appropriate, the local Mobile MCP provider.

### VS Code

Use native commands, editor, workspace and source-control APIs for normal operations. Use a Webview only when native APIs are insufficient; VS Code documents Webviews as a heavier, isolated UI mechanism.

### Android Studio

Build against the exact Android Studio / IntelliJ Platform target required by the adapter. JetBrains documents Android Studio plugin development through the IntelliJ Platform Gradle Plugin and product-specific dependencies.

Android Studio compatibility must be tested independently from Agent Execution Runtime core because IntelliJ Platform APIs change between releases.

## Packaging boundary

The Python repository contains the provider-neutral contract and registry. Native IDE packages are separate build artifacts.

MultiAgentOS
  +-- core/contracts/ide.py
  +-- runtime/ide/
  +-- integrations/ide/
      +-- xcode/
      +-- vscode/
      +-- android-studio/

Native adapter projects may remain isolated subprojects or later move to separate repositories. They must never add IDE SDK dependencies to the Python core.

## Implementation order

1. Provider-neutral contract and registry.
2. VS Code reference adapter.
3. Android Studio IntelliJ Platform adapter.
4. Xcode XcodeKit adapter.
5. Localhost bridge authentication and authorization.
6. Cross-IDE integration tests and packaging.
7. Marketplace / App Store distribution evaluation.

This phase is an integration surface, not a new Agent Execution Runtime runtime.
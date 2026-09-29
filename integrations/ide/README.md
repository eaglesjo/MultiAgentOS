# Agent Execution Runtime IDE Adapters

This directory is reserved for native IDE adapter projects.

- xcode/ — Swift/XcodeKit
- vscode/ — TypeScript/VS Code Extension API
- android-studio/ — Kotlin/JVM/IntelliJ Platform

Native IDE SDKs must remain isolated to their adapters. Do not import them into core/ or runtime/.

IDE adapters are optional integrations. Agent Execution Runtime core remains usable without an IDE installed.

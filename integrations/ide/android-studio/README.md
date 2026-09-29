# Agent Execution Runtime Android Studio Adapter

Thin IntelliJ Platform adapter for Agent Execution Runtime. Native Android Studio/IntelliJ APIs remain isolated in this module.

- Kotlin/JVM
- IntelliJ Platform plugin API
- IDE-originated context/events use the Agent Execution Runtime loopback bridge
- Agent Execution Runtime commands remain behind the adapter boundary
- Agent Execution Runtime core has no IntelliJ SDK dependency

Default bridge: http://127.0.0.1:8787

Endpoints:
- POST /v1/ide/event — IDE → Agent Execution Runtime
- POST /v1/ide/command — Agent Execution Runtime → IDE

Packaging and Marketplace distribution are later steps.

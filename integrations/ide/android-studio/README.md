# VYRELON Android Studio Adapter

Thin IntelliJ Platform adapter for VYRELON. Native Android Studio/IntelliJ APIs remain isolated in this module.

- Kotlin/JVM
- IntelliJ Platform plugin API
- IDE-originated context/events use the VYRELON loopback bridge
- VYRELON commands remain behind the adapter boundary
- VYRELON core has no IntelliJ SDK dependency

Default bridge: http://127.0.0.1:8787

Endpoints:
- POST /v1/ide/event — IDE → VYRELON
- POST /v1/ide/command — VYRELON → IDE

Packaging and Marketplace distribution are later steps.

# Agent Execution Runtime Facade

AgentExecutionRuntime is the project-facing runtime entry point.

It unifies:
- project profile inspection
- profile-specific agent catalog creation
- model-backed orchestration
- local Git runtime
- policy-controlled GitHub runtime
- GitHub connectivity probing
- multi-review panels

The facade keeps the underlying contracts and adapters modular while giving a project a single Agent Execution Runtime-owned control surface.


> **Compatibility note:** the filename and historical VYRELON implementation name are retained for compatibility. The architectural role is **Agent Execution Runtime**.

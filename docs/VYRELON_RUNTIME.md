# VYRELON Runtime Facade

VYRELONRuntime is the project-facing runtime entry point.

It unifies:
- project profile inspection
- profile-specific agent catalog creation
- model-backed orchestration
- local Git runtime
- policy-controlled GitHub runtime
- GitHub connectivity probing
- multi-review panels

The facade keeps the underlying contracts and adapters modular while giving a project a single VYRELON-owned control surface.

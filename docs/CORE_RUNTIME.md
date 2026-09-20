# VYRELON Core Runtime

The core runtime separates these concepts:

- **WorkUnit** — the unit of work being orchestrated, with a validated lifecycle.
- **AgentContract** — the role, capabilities, tools, permissions, and model preferences of an agent.
- **ModelSpec / AIProvider** — the AI implementation available to an agent.
- **AIRouter** — deterministic assignment with explicit preference followed by compatible fallback.
- **AgentExecutor / ResultVerifier** — vendor-neutral execution and verification boundaries.
- **LifecycleCoordinator** — executes delegated work and controls execution/verification state transitions.

## Multi-AI assignment

An agent may declare preferred model IDs. VYRELON first tries those models, then searches the registered model pool for a capability-compatible fallback.

This keeps agent roles independent from providers such as OpenAI, Anthropic, Google, local models, or future providers.

## Validation

The core runtime has no third-party test dependency:

```bash
python -m unittest discover -s tests -v
```

GitHub Actions provides CI on the public repository, while local execution remains the fastest development feedback loop.

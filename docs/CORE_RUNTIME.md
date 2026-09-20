# VYRELON Core Runtime

The first core runtime separates four concepts:

- **WorkUnit** — the unit of work being orchestrated.
- **AgentContract** — the role, capabilities, tools, permissions, and model preferences of an agent.
- **ModelSpec / AIProvider** — the AI implementation available to an agent.
- **AIRouter** — deterministic assignment with explicit preference followed by compatible fallback.

## Local-first validation

The core runtime has no network dependency and no third-party test framework.

Run:

```bash
python -m unittest discover -s tests -v
```

GitHub Actions remains an additional CI layer. Local execution is the primary development feedback loop while CI quota is unavailable.

## Multi-AI assignment

An agent may declare preferred model IDs. VYRELON first tries those models, then searches the registered model pool for a capability-compatible fallback.

This keeps agent roles independent from providers such as OpenAI, Anthropic, Google, local models, or future providers.

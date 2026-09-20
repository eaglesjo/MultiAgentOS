# VYRELON Multi-AI Assignment Configuration

VYRELON separates an Agent from the AI model used to execute that role.

Routing strategies:

- explicit: only the explicitly assigned model IDs are eligible.
- pool: try preferred models, then fall back to any compatible model.
- auto: ignore preferences and select a compatible model from the available pool.

A project can therefore assign multiple AIs to one role without hard-coding a vendor into the agent definition.

Example configuration is available at runtime/config/example.json.

The configuration contains provider/model identity, capabilities, adapter IDs, agent roles, and routing policy. Credentials remain outside the repository.

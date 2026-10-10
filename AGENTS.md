# Repository Agent Instructions

These instructions apply to all AI agents and coding assistants working in this repository, including delegated specialists and orchestration agents.

Before starting work, read [Agent Operating Principles](docs/AGENT_OPERATING_PRINCIPLES.md). Treat them as required workflow rules, not optional suggestions.

## Mandatory workflow

- Prefer direct execution with available authorized tools over asking the user to run commands.
- Verify the actual state after actions; do not rely only on tool success messages.
- Check available tool capabilities and authorization before declaring an action impossible or delegating it to the user.
- Include cleanup and cleanup verification for temporary resources.
- Report only evidence-backed outcomes and clearly mark pending, failed, blocked, or unverified work.
- Preserve repository protections, least privilege, and all required approval gates. Never bypass them to satisfy the direct-execution preference.

Before declaring completion, inspect the resulting diff/state, check relevant validation, and report the key evidence and any remaining limitations.

Agent-specific instructions may be more restrictive, but must not contradict these repository-wide requirements.

# Agent Plugin Marketplace

MultiAgentOS ships an **Agent Plugins 1.0** package in the repository root.

- `plugin.json`
- Portable skills under `skills/`
- Copilot-specific agents under `com.github.copilot/`
- Repository marketplace manifest: `.github/plugin/marketplace.json`

## GitHub Copilot CLI

```bash
copilot plugin marketplace add eaglesjo/MultiAgentOS
copilot plugin marketplace browse multiagentos
copilot plugin install multiagentos@multiagentos
```

## VS Code

Enable Agent Plugins and add `eaglesjo/MultiAgentOS` to `chat.plugins.marketplaces`.

For a direct smoke test, use **Chat: Install Plugin From Source** with:

`https://github.com/eaglesjo/MultiAgentOS`

Verify that `multiagentos-runtime` and the Copilot-specific `multiagentos` agent are available.

## Release policy

The plugin version follows the MultiAgentOS release version. The current codebase is **0.4.0** and remains unreleased until maintainer local acceptance passes.

The public release gate includes:

1. Python package installation.
2. Native macOS, Windows, and Ubuntu installation.
3. Copilot CLI plugin installation.
4. VS Code Agent Plugin installation.
5. Durable recovery behavior, including the human-review boundary.

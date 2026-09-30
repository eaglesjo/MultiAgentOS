# Agent Plugin Marketplace

MultiAgentOS ships an **Agent Plugins 1.0** package in the repository root.

The plugin manifest is:

- `plugin.json`
- Portable skills under `skills/`
- Copilot-specific agents under `com.github.copilot/`

The repository also contains a self-hosted Copilot plugin marketplace manifest at:

`.github/plugin/marketplace.json`

## Install from this repository

### GitHub Copilot CLI

Register the marketplace:

```bash
copilot plugin marketplace add eaglesjo/MultiAgentOS
```

Browse it:

```bash
copilot plugin marketplace browse multiagentos
```

Install the plugin:

```bash
copilot plugin install multiagentos@multiagentos
```

### VS Code

Enable Agent Plugins, then add `eaglesjo/MultiAgentOS` to the `chat.plugins.marketplaces` setting. The `multiagentos` plugin can then be discovered from the Agent Plugins UI.

For a pre-marketplace smoke test, VS Code also supports **Chat: Install Plugin From Source** using:

`https://github.com/eaglesjo/MultiAgentOS`

## Official GitHub Copilot marketplace submission

The default `copilot-plugins` marketplace is maintained by GitHub. MultiAgentOS can be submitted there as an external plugin entry referencing this canonical repository.

The intended entry is conceptually:

```json
{
  "name": "multiagentos",
  "description": "MultiAgentOS Agent Execution Runtime skills and local runtime integration for AI development tools.",
  "version": "0.4.0",
  "author": {
    "name": "eaglesjo"
  },
  "repository": "https://github.com/eaglesjo/MultiAgentOS",
  "license": "MIT",
  "source": {
    "source": "github",
    "repo": "eaglesjo/MultiAgentOS",
    "path": "."
  }
}
```

The official marketplace contribution is a separate change to `github/copilot-plugins`; it does not require copying the MultiAgentOS plugin into the MultiAgentOS repository.

## Release policy

The plugin version follows the MultiAgentOS release version. The current codebase is **0.4.0** and remains unreleased until the local acceptance gate passes.

Do not publish a public release or advertise the plugin as generally available solely because CI passes. The maintainer must first verify:

1. Python package installation.
2. Native macOS package installation.
3. Native Windows package installation.
4. Native Ubuntu package installation.
5. Copilot CLI plugin installation.
6. VS Code Agent Plugin installation.
7. Durable recovery behavior, including the human-review boundary for unresolved tool calls.

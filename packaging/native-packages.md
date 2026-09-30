# Native package test matrix

The native distribution is a thin launcher around the same MultiAgentOS CLI.

- macOS: architecture-specific installer-ready `.pkg`
- Windows: NSIS `.exe` installer
- Ubuntu: `.deb` package

The Agent Plugins package does not bundle another runtime. It references the installed `multiagentos` command so CLI and development tools share the same execution boundary.

Before a public release:

1. Build all native artifacts in GitHub Actions.
2. Download and install the artifact on the maintainer's local macOS machine.
3. Run `multiagentos --help`, `multiagentos status .`, MCP smoke tests, and recovery tests.
4. Install the Agent Plugin from the Git repository in VS Code/Copilot tooling and verify the bundled MCP server and skill.
5. Only after local acceptance, bump the package version and create the release tag.

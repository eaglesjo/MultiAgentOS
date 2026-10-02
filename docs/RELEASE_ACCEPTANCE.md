# Release Acceptance

MultiAgentOS uses a staged release gate.

## Gate 1 — CI

Required before local acceptance:

- contract tests
- install smoke
- Python wheel/sdist build
- native package matrix: macOS x64, macOS arm64, Windows x64, Ubuntu amd64
- Agent Plugin layout validation

## Gate 2 — Maintainer local installation

### Verified ChatGPT client boundary

| Client | GitHub | Local MCP | Result |
| --- | --- | --- | --- |
| ChatGPT Web | Yes | Yes | **Verified** |
| ChatGPT Mobile | Yes | No | **Verified** |

This records the capability observed in the current validation environment; it is not a universal guarantee across all ChatGPT plans or client configurations.


On the maintainer's macOS machine:

```bash
cd /Volumes/DevFiles/GitHubProject
git clone https://github.com/eaglesjo/MultiAgentOS.git MultiAgentOS-release-test
cd MultiAgentOS-release-test
git fetch origin main
git switch --detach origin/main
```

Python package smoke test:

```bash
python3 -m venv .venv-release-test
source .venv-release-test/bin/activate
python -m pip install --upgrade pip
python -m pip install .
multiagentos --help
multiagentos status .
python -m unittest discover -s tests -v
```

Native macOS package test:

1. Download the macOS artifact from the PR workflow.
2. Install the `.pkg`.
3. Open a new terminal.
4. Run `multiagentos --help`.
5. Run `multiagentos status <test-project>`.
6. Install the local Streamable HTTP MCP service with `multiagentos mcp install --path <test-project> --allow-write`.
7. Verify `multiagentos mcp status` reports the service as loaded.
8. Verify the service exposes `http://127.0.0.1:8000/mcp` and restarts after login/reboot.
9. Run the MCP stdio smoke test against a disposable project.
10. Verify a failed WorkUnit with an unresolved `tool_call` returns human-review-required rather than replaying the tool.

## Gate 3 — Development-tool plugin

In VS Code with Agent Plugins enabled:

1. Run **Chat: Install Plugin From Source**.
2. Enter `https://github.com/eaglesjo/MultiAgentOS`.
3. Verify the `multiagentos` plugin appears.
4. Verify the `multiagentos-runtime` skill is available.
5. Verify the `multiagentos` Copilot agent is available.
6. From a disposable project, ask the agent to inspect runtime state and use the installed `multiagentos` CLI.
7. Verify that recovery requests stop for human review when a durable tool call has no durable result.

## Gate 4 — Public release

Only after all local checks pass:

1. Bump `pyproject.toml` to the final semantic version.
2. Match the plugin version.
3. Update package acceptance expectations.
4. Merge the PR to `main`.
5. Create the matching `v<version>` tag.
6. Confirm PyPI publication.
7. Confirm the GitHub Release contains Python and native artifacts.
8. Verify the release install path again from a clean environment.

A public release must never be created merely because CI passed; the maintainer's local installation and IDE-plugin acceptance are explicit release gates.

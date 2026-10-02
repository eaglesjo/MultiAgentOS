# Changelog

## [0.4.2] - 2026-10-02

### Local MCP service

- Made local Streamable HTTP MCP the primary cost-free quick-start path.
- Documented the verified ChatGPT client boundary: ChatGPT Web can use GitHub and local MCP, while ChatGPT Mobile is verified for GitHub access only.
- Added `multiagentos mcp install`, `status`, and `uninstall` for macOS per-user `launchd` lifecycle management.
- The managed service listens on loopback and restarts automatically after login/reboot.
- Removed the Responses API / Secure MCP Tunnel smoke test from the core release path.
- Kept Secure MCP Tunnel as an optional remote integration rather than a baseline requirement.


All notable changes to MultiAgentOS are documented here.

## [0.4.1] - 2026-10-01

### Packaging and release metadata

- Corrected the PyPI project description source to use the repository README.
- Removed stale project identity text from the published metadata path.
- Added canonical Homepage, Repository, Documentation, Changelog, and Download links.
- Prepared the release workflow for a fresh PyPI and GitHub release.
- Updated installation guidance for macOS/Linux users to use `python3`.

## [0.4.0] - 2026-09-29

### Cost-free development baseline

- Enforced the COSTFREE-001 acceptance path in GitHub Actions.
- Verified clean-install bootstrap without a provider API key.
- Verified Agent Execution Runtime MCP initialization and tool discovery.
- Verified filesystem READ/WRITE through the MCP runtime.
- Verified unified patch application and readback.
- Verified shell/process execution through the Agent Execution Runtime MCP surface.
- Kept provider SDKs optional; the core package has no provider runtime dependency.
- Documented Secure MCP Tunnel integration and the current ChatGPT Web plan boundary.

### CI

- Added a dependency-free end-to-end acceptance harness.
- GitHub Actions now blocks the baseline when install, bootstrap, MCP, filesystem, patch, or process validation fails.

### Release scope

This release establishes the first explicit cost-free-by-default development baseline for MultiAgentOS. Paid AI providers, ChatGPT integrations, and other model clients remain optional integration layers.

## [0.3.0] - 2026-09-28

### Added

- Provider-neutral model capability discovery and normalization.
- Native provider discovery defaults for OpenAI, Anthropic, and Gemini.
- Persistent capability, quota, and health intelligence.
- Unified model control-plane state and operational event inspection.
- Quota-aware and health-aware model routing with cooldown recovery.
- Runtime observation of model usage and capabilities.
- Provider-neutral routing explainability through AIRouter.explain().
- Agent Execution Runtime routing explanation API and multiagentos models explain CLI.
- Model discovery and intelligence CLI commands.

### Compatibility

- Existing AIRouter.assign() behavior remains available.
- Provider-specific metadata is normalized before it reaches routing decisions.
- Provider credentials remain environment/configuration concerns and are not persisted by the runtime.

## [0.2.0]

The previous development baseline. See Git history for the detailed implementation sequence.

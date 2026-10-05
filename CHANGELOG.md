# Changelog

## [0.5.0] - 2026-10-05

### Agent orchestration and specialist runtime architecture

- Expanded the specialist catalog across architecture, backend/API/data, UX/UI, quality, security, performance, and operations.
- Preserved governance and specialist responsibilities as separate taxonomy layers.
- Kept orchestration as the core execution model: planning, delegation, execution, verification, review, and handoff.
- Preserved provider-neutral Agent × Model execution, recovery, audit identity, replay policy, and idempotency guarantees from the 0.4.x runtime line.
- Formalized platform-aware research and development specialist routing as the canonical agent taxonomy.
- Kept MCP and Tool capabilities as existing execution boundaries without expanding them as product architecture.
- Removed cost-free positioning from the core product architecture; deployment and provider cost remain operational concerns.

### Verification

- Specialist catalog contract coverage added for the expanded development disciplines.
- Recovery, replay-policy, tool identity, and idempotency regression coverage retained.
- Release gate requires the full test suite plus package/install validation before publishing the 0.5.0 release.


## [0.4.3] - 2026-10-03

### Project-scoped local MCP and Secure MCP Tunnel lifecycle

- Isolated managed local MCP services by project path so multiple projects can run independently.
- Hardened macOS MCP install/uninstall lifecycle handling and service identity.
- Bound Secure MCP Tunnel launchd services to explicit project MCP and health endpoints.
- Added project-scoped macOS tunnel status and uninstall scripts.
- Allowed project-scoped macOS tunnels for arbitrary project roots.
- Added lifecycle tests for macOS MCP services and tunnel launchd scripts.
- Preserved the Windows local MCP launcher behavior while isolating platform-specific tests.

### Verification

- Full test suite: 309 tests passed, 3 skipped on macOS.
- Verified managed MCP LaunchAgent remains running after macOS reboot/login.
- Verified project-scoped Secure MCP Tunnel launchd service remains running after reboot.
- Verified source distribution and wheel build successfully.
- Verified clean reinstall of the generated multiagentos-0.4.3 package and CLI startup.

## [0.4.2] - 2026-10-02

### Local MCP service

- Made local Streamable HTTP MCP the primary cost-free quick-start path.
- Documented the verified ChatGPT client boundary: ChatGPT Web can use GitHub and local MCP, while ChatGPT Mobile is verified for GitHub access only.
- Added `multiagentos mcp install`, `status`, and `uninstall` for OS-native local MCP lifecycle management.
- macOS uses per-user `launchd`; Windows uses per-user Task Scheduler.
- The managed service listens on loopback and starts automatically at user login.
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

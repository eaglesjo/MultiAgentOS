# Changelog

All notable changes to MultiAgentOS are documented here.

## [0.3.0] - 2026-09-28

### Added

- Provider-neutral model capability discovery and normalization.
- Native provider discovery defaults for OpenAI, Anthropic, and Gemini.
- Persistent capability, quota, and health intelligence.
- Unified model control-plane state and operational event inspection.
- Quota-aware and health-aware model routing with cooldown recovery.
- Runtime observation of model usage and capabilities.
- Provider-neutral routing explainability through AIRouter.explain().
- VYRELON routing explanation API and multiagentos models explain CLI.
- Model discovery and intelligence CLI commands.

### Compatibility

- Existing AIRouter.assign() behavior remains available.
- Provider-specific metadata is normalized before it reaches routing decisions.
- Provider credentials remain environment/configuration concerns and are not persisted by the runtime.

## [0.2.0]

The previous development baseline. See Git history for the detailed implementation sequence.

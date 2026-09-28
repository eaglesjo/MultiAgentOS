# Release Process

MultiAgentOS uses one repository with release-ready main and versioned GitHub Releases.

## Release gates

Before creating a release:

1. main must be green in GitHub Actions.
2. The full unittest suite must pass.
3. Provider discovery and routing explainability tests must pass.
4. README and CHANGELOG must describe the release surface.
5. The package version in pyproject.toml must match the release tag.
6. No credentials, provider secrets, prompt contents, or local .multiagentos runtime state may be committed.
7. Review the compare range from the previous release and verify backward compatibility.

## Versioning

Use semantic versioning:

- 0.x.y: pre-1.0 development releases.
- 1.0.0: first stable public API/runtime contract.
- Patch releases fix regressions without intentional API changes.
- Minor releases add backward-compatible capabilities.
- Major releases may change public contracts.

## Release sequence

1. Update pyproject.toml.
2. Update CHANGELOG.md.
3. Update README when the user-facing CLI or runtime surface changes.
4. Merge the release PR into main.
5. Wait for the post-merge GitHub Actions run to pass.
6. Create the matching Git tag and GitHub Release.
7. Record the release commit and validation result.

## Runtime state

.multiagentos/ is project-local runtime state. It contains persisted observations such as quota, health, capabilities, control events, sessions, and checkpoints. It is not release source data and must not be committed.

## First stable release

v1.0.0 should be created only after the public contracts, configuration compatibility, provider adapters, security boundaries, and release documentation have been validated together.

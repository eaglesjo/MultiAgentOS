# VYRELON GitHub Runtime

GitHub is a first-class lifecycle integration, but repository writes are policy-controlled.

## Layers

- core/contracts/github.py defines provider-neutral repository, branch, file, issue, PR, review, merge, and workflow contracts.
- integrations/github/gateway.py implements those contracts through the authenticated GitHub CLI.
- runtime/github.py applies VYRELON execution policy before allowing repository mutations.

## Policy

By default, GitHub writes are disabled.

When GitHub writes are enabled:

- branch/file/issue/review operations are permitted by the write capability
- PR creation requires explicit approval
- PR merge requires explicit approval

This keeps VYRELON capable of real GitHub development without silently granting an AI unrestricted repository mutation authority.

Authentication remains external to the repository through gh CLI authentication or the host environment.

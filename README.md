# MultiAgentOS

MultiAgentOS is the foundation for VYRELON, a local-first, GitHub-native multi-agent development orchestrator.

Principles:
- Local-first: filesystem, shell, processes and Git are first-class.
- GitHub-native: repository, branch, commit, issue, pull request and CI lifecycle are first-class.
- AI/Agent agnostic: no single model, vendor, IDE or agent is required.
- Role-based orchestration: work is delegated through explicit contracts.
- Multi-AI assignment: each agent/work unit can select providers/models with fallback and review strategies.
- Profile-driven: React Native, Android Native and iOS Native can extend the common core.

The first implementation establishes a provider-neutral GitHub gateway contract and a local GitHub CLI adapter. Authentication remains outside source control.

Status: VYRELON GitHub foundation.

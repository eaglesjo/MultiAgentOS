# Agent Execution Runtime Local Process and Git Runtime

Agent Execution Runtime treats local execution as a first-class runtime.

ProcessRuntime executes commands under ExecutionPolicy.

GitRuntime provides repository status/diff reads and policy-controlled branch/commit/push writes.

The default policy keeps Git writes disabled. Push requires explicit approval.

This keeps local repository mutation under Agent Execution Runtime policy rather than giving an AI adapter unrestricted shell authority.

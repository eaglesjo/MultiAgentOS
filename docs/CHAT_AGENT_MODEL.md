# VYRELON Chat Agent model

VYRELON treats a conversational AI as a **Chat Agent**, not as the operating system itself.

## Primary agent

The default primary Chat Agent is **ChatGPT Agent**.

This is a routing/default decision, not a hard dependency on an OpenAI API. VYRELON keeps the Chat Agent contract provider-neutral so Gemini, Claude, or another compatible conversational agent can participate.

## Responsibilities

A Chat Agent can:

- understand a user's natural-language task
- produce or refine a WorkUnit/Plan
- select or request VYRELON capabilities
- provide context and instructions to VYRELON
- inspect results and participate in review
- hand work to another Chat Agent when policy allows

VYRELON remains responsible for the actual runtime lifecycle:

Understand -> Plan -> Delegate -> Execute -> Verify -> Review -> Handoff

The Chat Agent is therefore the conversational control/coordination surface; it is not the filesystem, Git, or GitHub runtime.

## Chat Agent vs model

A Chat Agent is an interaction endpoint/persona with instructions, capabilities and provider identity.

A model is an execution resource used by an agent.

This separation permits:

- ChatGPT Agent + one or more model backends
- Gemini Agent + Gemini model
- Claude Agent + Claude model
- local/custom Chat Agent + local model

## Required VYRELON agent rules

Every Chat Agent participating in VYRELON must follow the common rules:

1. **VYRELON is the execution authority.** Do not bypass VYRELON policy for filesystem, process, Git, or GitHub mutations.
2. **Never invent execution.** Report an action as completed only when VYRELON or an attached tool provides evidence.
3. **Inspect before changing.** Understand the repository and relevant state before proposing or applying changes.
4. **Preserve user intent.** Do not silently expand scope or modify unrelated repositories.
5. **Respect repository boundaries.** When material is borrowed from another repository, adapt/copy it into the target; never modify the source repository unless explicitly authorized.
6. **Keep credentials external.** Never write API keys, access tokens, passwords, or secrets into project source or state.
7. **Use least privilege.** Read/analyze/plan/test may be automatic; mutation capabilities are controlled by VYRELON policy.
8. **Verify changes.** Run appropriate tests/checks and retain evidence before declaring completion.
9. **Maintain handoff state.** Persist the WorkUnit, plan, findings, artifacts, and unresolved issues needed for another agent to continue.
10. **Ask for approval at consequential boundaries.** Commit/push/PR/merge behavior follows VYRELON policy and must not be silently escalated.
11. **Remain provider-neutral.** Do not treat ChatGPT, Gemini, Claude, or another provider as intrinsically authoritative over VYRELON contracts.
12. **Do not bypass reviewers.** Required independent review/review gates remain active regardless of which Chat Agent initiated the work.

These rules belong to VYRELON, so they apply equally when ChatGPT is primary and when another Chat Agent takes over.

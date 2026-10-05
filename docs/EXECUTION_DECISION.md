# Execution Decision Contract

`ExecutionDecision` is the final, immutable authorization snapshot immediately before an Agent executes a Model.

## Decision inputs

The contract binds:

1. the WorkUnit and route stage;
2. the selected Agent and its selection confidence/source;
3. the resolved Model and full `RoutingExplanation`;
4. governance findings;
5. health and quota availability;
6. adaptive execution attempt.

The decision is authorized only when governance passes and the selected model is compatible, healthy, and quota-available.

## Runtime boundary

```text
AgentPlan
   |
   v
AgentModelResolver
   |
   v
ExecutionDecision.authorize()
   |
   +-- denied --> no AgentExecutor call
   |
   +-- authorized --> exact Agent x Model execution
                         |
                         v
                    execution evidence
                         |
                         v
                    Health / Quota feedback
```

The runtime persists the decision in:

`WorkUnit.metadata["execution_decisions"]`

Each record contains a deterministic `decision_id`, so the same decision inputs produce the same identifier.

## Adaptive retry

A retry writes a new execution decision for the affected stage with the next `execution_attempt`. Governance stages are not adaptively replaced, and the decision remains stage-local.

This makes the runtime audit trail answer:

> Why did this Agent execute with this Model on this attempt?

without reconstructing the decision from mutable routing state.

# VYRELON Planning and State

VYRELON has explicit planning contracts and persistent WorkUnit state.

Planning:
- BasicPlanner moves a WorkUnit from PENDING to PLANNING.
- WorkPlan contains dependency-aware PlanStep records.
- Invalid dependencies are rejected.

State:
- WorkStateStore persists WorkUnit state under .multiagentos/state/.
- State can be restored after a process or session restart.

This gives the orchestration loop continuity instead of relying on in-memory chat context.

"""Durable execution cursor contract."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionCursor:
    work_unit_id: str
    event_sequence: int
    round_number: int
    agent_id: str
    model_id: str | None = None
    conversation_revision: int = 0
    next_tool_call_id: str | None = None

    def advances_from(self, previous: "ExecutionCursor") -> bool:
        return (
            self.work_unit_id == previous.work_unit_id
            and self.event_sequence > previous.event_sequence
            and self.conversation_revision >= previous.conversation_revision
        )

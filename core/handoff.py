"""Handoff and multi-review coordination."""

from dataclasses import dataclass

from core.contracts.agent import AgentContract
from core.contracts.handoff import HandoffArtifact, ReviewResult


class HandoffManager:
    def create(self, work_unit_id, from_agent, to_agent, summary, artifacts=None, findings=None):
        return HandoffArtifact(
            work_unit_id=work_unit_id,
            from_agent=from_agent.id,
            to_agent=to_agent.id,
            summary=summary,
            artifacts=tuple(artifacts or ()),
            findings=tuple(findings or ()),
        )


@dataclass(frozen=True)
class ReviewPanelResult:
    approved: bool
    reviews: tuple[ReviewResult, ...]
    consensus: str


class ReviewPanel:
    def review(self, work_unit_id, reviewers, reviewer_runner):
        reviews = tuple(
            reviewer_runner(review_work_unit_id=work_unit_id, reviewer=reviewer, context=context)
            for reviewer, context in reviewers
        )
        approved = bool(reviews) and all(review.approved for review in reviews)
        return ReviewPanelResult(
            approved=approved,
            reviews=reviews,
            consensus="approved" if approved else "changes-requested",
        )

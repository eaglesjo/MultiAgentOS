"""Handoff and multi-review coordination."""

from concurrent.futures import ThreadPoolExecutor
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
    def review(self, work_unit_id, reviewers, reviewer_runner, parallel=True):
        def run(item):
            reviewer, context = item
            return reviewer_runner(review_work_unit_id=work_unit_id, reviewer=reviewer, context=context)
        if parallel and len(reviewers) > 1:
            with ThreadPoolExecutor(max_workers=len(reviewers)) as pool:
                reviews = tuple(pool.map(run, reviewers))
        else:
            reviews = tuple(run(item) for item in reviewers)
        approved = bool(reviews) and all(review.approved for review in reviews)
        return ReviewPanelResult(
            approved=approved,
            reviews=reviews,
            consensus="approved" if approved else "changes-requested",
        )

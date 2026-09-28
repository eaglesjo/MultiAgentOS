"""Handoff and multi-review coordination."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from core.contracts.agent import AgentContract
from core.contracts.handoff import HandoffArtifact, ReviewContext, ReviewResult


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
    def review(self, work_unit_id, reviewers, reviewer_runner, parallel=True, context=None):
        def run(item):
            reviewer, reviewer_context = item
            merged_context = dict(reviewer_context or {})
            if context is not None:
                if isinstance(context, ReviewContext):
                    merged_context.update({
                        "work_unit_id": context.work_unit_id,
                        "artifact_ids": context.artifact_ids,
                        "findings": context.findings,
                        "last_agent_id": context.last_agent_id,
                        "review_cycle": context.review_cycle,
                        "metadata": context.metadata,
                    })
                else:
                    merged_context.update(dict(context))
            result = reviewer_runner(
                review_work_unit_id=work_unit_id,
                reviewer=reviewer,
                context=merged_context,
            )
            if hasattr(result, "reviewer_id"):
                return result
            return ReviewResult(
                reviewer_id=reviewer.id,
                approved=bool(result.approved),
                feedback=str(getattr(result, "feedback", "")),
            )
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

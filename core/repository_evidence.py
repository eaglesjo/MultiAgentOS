"""Repository-backed evidence adapters for Agent selection.

The selector stays provider-neutral: RepositoryRuntime produces repository
evidence, while this module translates that evidence into the bounded
EvidenceRecord contract used by routing policy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.contracts.evidence import EvidenceKind, EvidenceRecord
from core.contracts.repository import RepositoryEvidence
from core.contracts.work_unit import WorkUnit


_CHANGED_PATH = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class RepositoryEvidenceProvider:
    """Convert RepositoryRuntime evidence into selector evidence."""

    def collect(
        self,
        work_unit: WorkUnit,
        repository_evidence: RepositoryEvidence | None = None,
    ) -> tuple[EvidenceRecord, ...]:
        if repository_evidence is None:
            return ()

        records: list[EvidenceRecord] = []

        def add(
            source: str,
            evidence_type: str,
            value: str,
            *,
            strength: str = "strong",
            kind: EvidenceKind = EvidenceKind.FACT,
        ) -> None:
            if not value.strip():
                return
            records.append(
                EvidenceRecord(
                    id=f"repository-{work_unit.id}-{len(records) + 1}",
                    work_unit_id=work_unit.id,
                    kind=kind,
                    source=source,
                    statement=f"{evidence_type}={value}",
                    metadata={
                        "evidence_type": evidence_type,
                        "value": value,
                        "strength": strength,
                    },
                )
            )

        if repository_evidence.git_status.strip():
            add("repository.git_status", "git_status", "dirty")
        else:
            add("repository.git_status", "git_status", "clean")

        changed_paths = tuple(dict.fromkeys(_CHANGED_PATH.findall(repository_evidence.git_diff)))
        if changed_paths:
            add(
                "repository.git_diff",
                "changed_paths",
                ",".join(changed_paths[:50]),
                strength="strong",
            )

        workflows = repository_evidence.workflows
        if workflows:
            add(
                "repository.workflows",
                "workflow_count",
                str(len(workflows)),
                strength="medium",
            )

        validation = repository_evidence.validation or {}
        for key in ("platform", "technology", "framework", "language"):
            value = validation.get(key)
            if isinstance(value, str):
                add(
                    f"repository.validation.{key}",
                    key,
                    value,
                    strength="strong",
                    kind=EvidenceKind.VERIFIED,
                )

        if repository_evidence.checkpoint_id:
            add(
                "repository.checkpoint",
                "checkpoint",
                repository_evidence.checkpoint_id,
                strength="medium",
            )

        return tuple(records)

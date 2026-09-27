"""Provider-neutral validation runtime for VYRELON."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from runtime.local.shell import PersistentShellRuntime
from runtime.policy import ExecutionPolicy


@dataclass(frozen=True)
class ValidationStep:
    id: str
    command: str
    kind: str = "test"
    required: bool = True
    timeout: float = 120.0


@dataclass(frozen=True)
class ValidationResult:
    step_id: str
    command: str
    kind: str
    returncode: int
    stdout: str
    stderr: str
    passed: bool
    required: bool

    @property
    def evidence(self) -> dict[str, object]:
        return {
            "step_id": self.step_id,
            "command": self.command,
            "kind": self.kind,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "passed": self.passed,
            "required": self.required,
        }


@dataclass(frozen=True)
class ValidationReport:
    project_root: str
    results: tuple[ValidationResult, ...]
    passed: bool
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def evidence(self) -> dict[str, object]:
        return {
            "project_root": self.project_root,
            "passed": self.passed,
            "results": [result.evidence for result in self.results],
            "metadata": dict(self.metadata),
        }

    def persist(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.evidence, indent=2, ensure_ascii=False) + "\n")
        return path


class ValidationRuntime:
    """Execute deterministic project validation through VYRELON's local tool boundary."""

    def __init__(self, policy: ExecutionPolicy | None = None) -> None:
        self.policy = policy or ExecutionPolicy()

    def run(
        self,
        project_root: Path,
        steps: Iterable[ValidationStep],
        *,
        persist_evidence: bool = True,
    ) -> ValidationReport:
        shell = PersistentShellRuntime(str(project_root), policy=self.policy)
        results: list[ValidationResult] = []

        for step in steps:
            try:
                output = shell.run(step.command, timeout=step.timeout)
                result = ValidationResult(
                    step_id=step.id,
                    command=step.command,
                    kind=step.kind,
                    returncode=output.returncode,
                    stdout=output.stdout,
                    stderr=output.stderr,
                    passed=output.returncode == 0,
                    required=step.required,
                )
            except Exception as exc:
                result = ValidationResult(
                    step_id=step.id,
                    command=step.command,
                    kind=step.kind,
                    returncode=-1,
                    stdout="",
                    stderr=str(exc),
                    passed=False,
                    required=step.required,
                )
            results.append(result)

        passed = all(result.passed for result in results if result.required)
        report = ValidationReport(
            project_root=str(project_root),
            results=tuple(results),
            passed=passed,
            metadata={"runtime": "vyrelon-validation"},
        )
        if persist_evidence:
            report.persist(project_root / ".multiagentos" / "evidence" / "validation.json")
        return report

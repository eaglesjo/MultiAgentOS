"""Agent execution helpers for IDE-originated coding work."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.contracts.agent import AgentContract
from core.contracts.execution import AgentExecutor
from core.contracts.work_unit import WorkUnit
from core.contracts.model_runtime import ModelResponse
from runtime.local.patch import PatchRuntime
from runtime.policy import ExecutionPolicy
from runtime.validation import ValidationReport, ValidationRuntime, ValidationStep


@dataclass
class IDECodingExecutor:
    """Execute a model request and optionally materialize its patch into the project."""

    delegate: AgentExecutor
    project_root: Path
    apply_changes: bool = False
    policy: ExecutionPolicy | None = None

    def execute(self, *, agent: AgentContract, model_id: str, work_unit: WorkUnit) -> object:
        output = self.delegate.execute(agent=agent, model_id=model_id, work_unit=work_unit)
        if not isinstance(output, ModelResponse):
            return output

        patch = output.metadata.get("patch")
        if patch is None:
            work_unit.metadata["code_change"] = False
            return output

        if not isinstance(patch, str) or not patch.strip():
            raise ValueError("model patch metadata must be a non-empty string")

        work_unit.metadata["code_change"] = True
        work_unit.metadata["patch"] = patch
        if not self.apply_changes:
            work_unit.metadata["patch_applied"] = False
            work_unit.metadata["patch_requires_approval"] = True
            return output

        result = PatchRuntime(
            policy=self.policy,
        ).apply(str(self.project_root), patch, approved=True)
        work_unit.metadata["patch_returncode"] = result.returncode
        work_unit.metadata["patch_stdout"] = result.stdout
        work_unit.metadata["patch_stderr"] = result.stderr
        if result.returncode != 0:
            raise RuntimeError(f"patch application failed: {result.stderr or result.stdout}")
        work_unit.metadata["patch_applied"] = True
        return output


@dataclass
class IDEValidationVerifier:
    """Validate an IDE-originated code change using VYRELON's local validation boundary."""

    project_root: Path
    commands: tuple[str, ...]
    policy: ExecutionPolicy | None = None

    def verify(self, *, work_unit: WorkUnit, output: object) -> bool:
        if not self.commands:
            work_unit.metadata["validation_skipped"] = True
            return True
        report: ValidationReport = ValidationRuntime(self.policy).run(
            self.project_root,
            (
                ValidationStep(id=f"ide-validation-{index}", command=command)
                for index, command in enumerate(self.commands, start=1)
            ),
        )
        work_unit.metadata["validation_passed"] = report.passed
        work_unit.metadata["validation_evidence"] = report.evidence
        return report.passed

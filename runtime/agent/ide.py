"""Agent execution helpers for IDE-originated coding work."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.contracts.agent import AgentContract
from core.contracts.execution import AgentExecutor
from core.contracts.work_unit import WorkUnit
from core.contracts.model_runtime import ModelResponse
from runtime.tool_calling import ToolRuntime
from runtime.policy import ExecutionPolicy
from runtime.validation import ValidationReport, ValidationRuntime, ValidationStep


@dataclass
class IDECodingExecutor:
    """Execute a model request and optionally materialize its patch into the project."""

    delegate: AgentExecutor
    project_root: Path
    apply_changes: bool = False
    policy: ExecutionPolicy | None = None
    tool_runtime: ToolRuntime | None = None

    def execute(self, *, agent: AgentContract, model_id: str, work_unit: WorkUnit) -> object:
        execute_with_tools = getattr(self.delegate, "execute_with_tools", None)
        if self.tool_runtime is not None and callable(execute_with_tools):
            execution = execute_with_tools(
                agent=agent,
                model_id=model_id,
                work_unit=work_unit,
                tool_runtime=self.tool_runtime,
                approved=self.apply_changes,
            )
            output = execution.response
            changed = any(
                result.tool_id == "patch.apply" and result.ok
                for result in execution.tool_results
            )
            work_unit.metadata["code_change"] = changed
            work_unit.metadata["patch_applied"] = changed
            return output

        output = self.delegate.execute(agent=agent, model_id=model_id, work_unit=work_unit)
        if not isinstance(output, ModelResponse):
            return output
        work_unit.metadata["code_change"] = False
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

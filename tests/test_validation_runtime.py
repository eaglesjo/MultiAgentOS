from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from runtime.policy import ExecutionPolicy
from runtime.validation import ValidationRuntime, ValidationStep


class ValidationRuntimeTests(TestCase):
    def test_runs_steps_and_persists_evidence(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = ValidationRuntime().run(root, [
                ValidationStep("test", "python -c \"print('ok')\"", kind="test"),
                ValidationStep("lint", "python -c \"print('lint')\"", kind="lint"),
            ])
            self.assertTrue(report.passed)
            self.assertEqual(len(report.results), 2)
            self.assertTrue((root / ".multiagentos/evidence/validation.json").exists())

    def test_required_failure_fails_report_but_optional_failure_does_not(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = ValidationRuntime().run(root, [
                ValidationStep("required", "python -c \"raise SystemExit(2)\"", required=True),
                ValidationStep("optional", "python -c \"raise SystemExit(3)\"", required=False),
            ], persist_evidence=False)
            self.assertFalse(report.passed)
            self.assertEqual(report.results[0].returncode, 2)
            self.assertFalse(report.results[1].passed)

    def test_process_policy_is_enforced(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = ValidationRuntime(
                ExecutionPolicy(allow_process=False)
            ).run(root, [
                ValidationStep("test", "python -c \"print('no')\"")
            ], persist_evidence=False)
            self.assertFalse(report.passed)
            self.assertIn("disabled", report.results[0].stderr)

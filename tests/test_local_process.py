import unittest

from core.contracts import AgentContract, WorkUnit
from core.contracts.runtime import ExecutionRequest
from runtime.local.process import LocalProcessExecutor
from runtime.policy import ExecutionPolicy


class LocalProcessExecutorTests(unittest.TestCase):
    def setUp(self):
        self.request = ExecutionRequest(
            agent=AgentContract(id="developer", role="developer"),
            model_id="local",
            work_unit=WorkUnit(
                id="wu-process",
                objective="run validation",
                inputs={"command": ["python", "-c", "print('ok')"]},
            ),
        )

    def test_executes_explicit_argv(self):
        result = LocalProcessExecutor().execute(self.request)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_policy_can_disable_processes(self):
        executor = LocalProcessExecutor(ExecutionPolicy(allow_process=False))
        with self.assertRaises(PermissionError):
            executor.execute(self.request)

    def test_rejects_shell_style_string(self):
        self.request.work_unit.inputs["command"] = "python -c print('bad')"
        with self.assertRaises(ValueError):
            LocalProcessExecutor().execute(self.request)


if __name__ == "__main__":
    unittest.main()

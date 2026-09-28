import tempfile
import unittest
from pathlib import Path

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.checkpoint import WorkflowCheckpoint
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.lifecycle import ExecutionInterrupted
from core.state import WorkStateStore
from runtime.vyrelon import VYRELONRuntime


class InterruptingExecutor:
    def execute(self, *, agent, model_id, work_unit):
        raise ExecutionInterrupted("simulated process interruption")


class CheckpointExecutor:
    def execute(self, *, agent, model_id, work_unit):
        return {"agent": agent.id}



class UnifiedCheckpointTests(unittest.TestCase):
    def test_checkpoint_store_round_trips_structured_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkStateStore(Path(directory) / ".multiagentos" / "state")
            work_unit = WorkUnit("wu-checkpoint", "checkpoint contract")
            checkpoint = store.checkpoint(
                work_unit,
                workflow="orchestration",
                stage="executing",
                sequence=1,
                next_action="resume_execution",
                agent_ids=("developer",),
                model_ids=("local",),
            )

            loaded = store.load_checkpoint(work_unit.id)

            self.assertEqual(loaded, checkpoint)
            self.assertEqual(loaded.next_action, "resume_execution")
            self.assertTrue(loaded.resumable)

    def test_lifecycle_interruption_persists_a_resumable_checkpoint(self):
        runtime = VYRELONRuntime()
        agent = AgentContract(id="developer", role="developer")
        models = [ModelSpec("local", "local", frozenset())]
        work_unit = WorkUnit("wu-interrupted", "persist interrupted execution")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ExecutionInterrupted):
                runtime.run(
                    work_unit,
                    agent,
                    models,
                    InterruptingExecutor(),
                    project_root=root,
                )

            fresh = VYRELONRuntime()
            persisted = fresh.state_store(root).load(work_unit.id)
            checkpoint = fresh.load_checkpoint(work_unit.id, root)

            self.assertEqual(persisted.status, WorkStatus.EXECUTING)
            self.assertEqual(checkpoint.status, WorkStatus.EXECUTING.value)
            self.assertEqual(checkpoint.workflow, "orchestration")
            self.assertEqual(checkpoint.stage, WorkStatus.EXECUTING.value)
            self.assertEqual(checkpoint.next_action, "resume_execution")
            self.assertEqual(checkpoint.agent_ids, ("developer",))
            self.assertEqual(checkpoint.model_ids, ("local",))

            resumed = fresh.resume_workflow(
                work_unit.id,
                agent,
                models,
                CheckpointExecutor(),
                project_root=root,
            )
            self.assertEqual(resumed.work_unit.status, WorkStatus.COMPLETED)
            completed_checkpoint = fresh.load_checkpoint(work_unit.id, root)
            self.assertFalse(completed_checkpoint.resumable)
            self.assertEqual(completed_checkpoint.status, WorkStatus.COMPLETED.value)

    def test_checkpoint_contract_rejects_invalid_schema(self):
        with self.assertRaises(ValueError):
            WorkflowCheckpoint(
                schema_version=0,
                work_unit_id="wu",
                workflow="test",
                status="executing",
                stage="executing",
            ).validate()


    def test_multi_agent_resume_starts_at_checkpointed_stage(self):
        class InterruptOnceExecutor:
            def __init__(self):
                self.calls = []

            def execute(self, *, agent, model_id, work_unit):
                self.calls.append(agent.id)
                if agent.id == "developer":
                    raise ExecutionInterrupted("stage interrupted")
                return {"agent": agent.id}

        agents = [
            AgentContract(id="planner", role="planner"),
            AgentContract(id="developer", role="developer"),
            AgentContract(id="tester", role="tester"),
        ]
        models = [ModelSpec("local", "local", frozenset())]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = VYRELONRuntime()
            work_unit = WorkUnit("wu-stage-resume", "resume from developer")
            executor = InterruptOnceExecutor()

            with self.assertRaises(ExecutionInterrupted):
                runtime.run_multi_agent_workflow(
                    work_unit=work_unit,
                    stages=agents,
                    models=models,
                    executor=executor,
                    project_root=root,
                )

            checkpoint = runtime.load_checkpoint(work_unit.id, root)
            self.assertEqual(checkpoint.workflow, "multi_agent")
            self.assertEqual(checkpoint.next_action, "execute_stage")
            self.assertEqual(checkpoint.metadata["next_stage_index"], 1)

            resumed = runtime.resume_multi_agent_workflow(
                work_unit.id,
                stages=agents,
                models=models,
                executor=CheckpointExecutor(),
                project_root=root,
            )
            self.assertEqual(resumed.work_unit.status, WorkStatus.COMPLETED)
            self.assertEqual(
                [stage.agent_id for stage in resumed.stages],
                ["developer", "tester"],
            )


if __name__ == "__main__":
    unittest.main()

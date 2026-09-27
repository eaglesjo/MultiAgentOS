import unittest

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelResponse
from core.contracts.work_unit import WorkUnit
from runtime.agent.model import ModelAgentExecutor


class FailingAdapter:
    def generate(self, model, request):
        error = RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")
        error.status_code = 429
        raise error


class WorkingAdapter:
    def generate(self, model, request):
        return ModelResponse(text="fallback ok", model_id=model.id, metadata={})


class ModelFailoverTests(unittest.TestCase):
    def test_quota_failure_moves_to_compatible_fallback(self):
        models = [
            ModelSpec(id="primary", provider_id="p1", capabilities=frozenset({"code"})),
            ModelSpec(id="fallback", provider_id="p2", capabilities=frozenset({"code"})),
        ]
        executor = ModelAgentExecutor(
            adapters={"p1": FailingAdapter(), "p2": WorkingAdapter()},
            models=models,
            fallback_model_ids=("fallback",),
        )
        agent = AgentContract(
            id="developer",
            role="developer",
            capabilities=frozenset({"code"}),
        )
        work = WorkUnit(id="failover", objective="do the work")

        result = executor.execute(agent=agent, model_id="primary", work_unit=work)

        self.assertEqual(result.model_id, "fallback")
        self.assertEqual(work.metadata["model_attempts"], ("primary", "fallback"))

    def test_non_retryable_error_does_not_switch_model(self):
        class InvalidRequestAdapter:
            def generate(self, model, request):
                raise ValueError("400 invalid request")

        models = [
            ModelSpec(id="primary", provider_id="p1", capabilities=frozenset({"code"})),
            ModelSpec(id="fallback", provider_id="p2", capabilities=frozenset({"code"})),
        ]
        executor = ModelAgentExecutor(
            adapters={"p1": InvalidRequestAdapter(), "p2": WorkingAdapter()},
            models=models,
            fallback_model_ids=("fallback",),
        )
        agent = AgentContract(id="developer", role="developer")
        work = WorkUnit(id="no-failover", objective="do the work")

        with self.assertRaises(ValueError):
            executor.execute(agent=agent, model_id="primary", work_unit=work)


if __name__ == "__main__":
    unittest.main()

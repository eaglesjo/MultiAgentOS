"""Tests for the provider-neutral VYRELON AI runtime."""

import unittest

from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelRequest, ModelResponse
from core.contracts.vyrelon_runtime import (
    FallbackPolicy,
    RuntimeEventKind,
    SessionSpec,
)
from runtime.model.ai_runtime import AIExecutionError, AIRuntime


class StubAdapter:
    def __init__(self, *, text: str = "ok", failures: int = 0) -> None:
        self.text = text
        self.failures = failures
        self.calls = 0

    def generate(self, model, request):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("transient")
        return ModelResponse(text=self.text, model_id=model.id)


class AIRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.models = {
            "primary": ModelSpec(id="primary", provider_id="provider"),
            "backup": ModelSpec(id="backup", provider_id="provider"),
        }

    def test_executes_selected_model(self):
        adapter = StubAdapter(text="hello")
        runtime = AIRuntime(models=self.models, adapters={"primary": adapter})
        result = runtime.execute(ModelRequest(prompt="hello"), model_id="primary")
        self.assertEqual(result.response.text, "hello")
        self.assertEqual(result.model_id, "primary")
        self.assertEqual(result.attempts, ("primary",))

    def test_fallback_uses_ordered_candidates(self):
        primary = StubAdapter(failures=1)
        backup = StubAdapter(text="backup")
        runtime = AIRuntime(
            models=self.models, adapters={"primary": primary, "backup": backup}
        )
        policy = FallbackPolicy(
            model_ids=("primary", "backup"),
            retryable_errors=frozenset({"RuntimeError"}),
        )
        result = runtime.execute(
            ModelRequest(prompt="hello"),
            model_id="primary",
            fallback=policy,
        )
        self.assertEqual(result.model_id, "backup")
        self.assertEqual(result.attempts, ("primary", "backup"))

    def test_non_retryable_error_stops_fallback(self):
        primary = StubAdapter(failures=1)
        backup = StubAdapter(text="backup")
        runtime = AIRuntime(
            models=self.models, adapters={"primary": primary, "backup": backup}
        )
        policy = FallbackPolicy(
            model_ids=("primary", "backup"),
            retryable_errors=frozenset(),
        )
        with self.assertRaises(RuntimeError):
            runtime.execute(
                ModelRequest(prompt="hello"),
                model_id="primary",
                fallback=policy,
            )
        self.assertEqual(backup.calls, 0)

    def test_events_have_ordered_lifecycle(self):
        runtime = AIRuntime(
            models=self.models,
            adapters={"primary": StubAdapter(text="hello")},
        )
        events = list(
            runtime.events(
                ModelRequest(prompt="hello"),
                model_id="primary",
                session=SessionSpec(id="s1", project_root="/workspace"),
            )
        )
        self.assertEqual(
            [event.kind for event in events],
            [
                RuntimeEventKind.REQUEST,
                RuntimeEventKind.MESSAGE,
                RuntimeEventKind.COMPLETED,
            ],
        )
        self.assertEqual([event.sequence for event in events], [1, 2, 3])

    def test_exhausted_fallback_reports_attempts(self):
        primary = StubAdapter(failures=1)
        backup = StubAdapter(failures=1)
        runtime = AIRuntime(
            models=self.models, adapters={"primary": primary, "backup": backup}
        )
        policy = FallbackPolicy(
            model_ids=("primary", "backup"),
            retryable_errors=frozenset({"RuntimeError"}),
        )
        with self.assertRaises(AIExecutionError) as ctx:
            runtime.execute(
                ModelRequest(prompt="hello"),
                model_id="primary",
                fallback=policy,
            )
        self.assertEqual(ctx.exception.attempts, ("primary", "backup"))


if __name__ == "__main__":
    unittest.main()

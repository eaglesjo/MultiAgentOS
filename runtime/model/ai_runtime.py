"""Provider-neutral AI execution runtime for AGENT_EXECUTION_RUNTIME."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelAdapter, ModelRequest, ModelResponse
from core.contracts.agent_execution_runtime import (
    FallbackPolicy,
    RuntimeEvent,
    RuntimeEventKind,
    SessionSpec,
)


class AIRuntimeError(RuntimeError):
    """Base error raised by the AGENT_EXECUTION_RUNTIME AI runtime."""


class AIExecutionError(AIRuntimeError):
    """Raised when all configured model attempts fail."""

    def __init__(self, message: str, *, attempts: tuple[str, ...]) -> None:
        super().__init__(message)
        self.attempts = attempts


@dataclass(frozen=True)
class AIExecution:
    """Normalized result of one AI runtime invocation."""

    response: ModelResponse
    model_id: str
    attempts: tuple[str, ...]


class AIRuntime:
    """Execute provider-neutral model adapters without a harness abstraction."""

    def __init__(
        self,
        *,
        models: dict[str, ModelSpec],
        adapters: dict[str, ModelAdapter],
    ) -> None:
        self._models = models
        self._adapters = adapters

    def execute(
        self,
        request: ModelRequest,
        *,
        model_id: str,
        session: SessionSpec | None = None,
        fallback: FallbackPolicy | None = None,
    ) -> AIExecution:
        candidates = self._candidates(model_id, fallback)
        attempts: list[str] = []
        errors: list[str] = []

        for candidate in candidates:
            attempts.append(candidate)
            model = self._model(candidate)
            adapter = self._adapter(model)
            try:
                response = adapter.generate(model, request)
            except Exception as exc:
                if not self._retryable(exc, fallback):
                    raise
                errors.append(f"{candidate}: {exc}")
                continue

            metadata = dict(response.metadata)
            metadata.update(
                {"provider_id": model.provider_id, "attempts": tuple(attempts)}
            )
            if session is not None:
                metadata["session_id"] = session.id
            normalized = ModelResponse(
                text=response.text,
                model_id=response.model_id or candidate,
                metadata=metadata,
            )
            return AIExecution(
                response=normalized,
                model_id=normalized.model_id,
                attempts=tuple(attempts),
            )

        detail = "; ".join(errors) if errors else "no model candidates"
        raise AIExecutionError(
            f"AI execution failed: {detail}",
            attempts=tuple(attempts),
        )

    def events(
        self,
        request: ModelRequest,
        *,
        model_id: str,
        session: SessionSpec | None = None,
        fallback: FallbackPolicy | None = None,
    ) -> Iterator[RuntimeEvent]:
        """Expose normalized lifecycle events around a model invocation."""
        sequence = 0

        def emit(kind: RuntimeEventKind, payload: object = None):
            nonlocal sequence
            sequence += 1
            return RuntimeEvent(
                kind=kind,
                session_id=session.id if session else None,
                payload=payload,
                sequence=sequence,
            )

        yield emit(RuntimeEventKind.REQUEST, {"model_id": model_id})
        try:
            execution = self.execute(
                request,
                model_id=model_id,
                session=session,
                fallback=fallback,
            )
            yield emit(
                RuntimeEventKind.MESSAGE,
                {"model_id": execution.model_id, "text": execution.response.text},
            )
            yield emit(
                RuntimeEventKind.COMPLETED,
                {"model_id": execution.model_id, "attempts": execution.attempts},
            )
        except Exception as exc:
            yield emit(RuntimeEventKind.ERROR, {"error": str(exc)})
            raise

    def _candidates(
        self, model_id: str, fallback: FallbackPolicy | None
    ) -> tuple[str, ...]:
        if fallback is None:
            return (model_id,)
        candidates = fallback.candidates()
        return candidates or (model_id,)

    def _model(self, model_id: str) -> ModelSpec:
        try:
            return self._models[model_id]
        except KeyError as exc:
            raise AIRuntimeError(f"Model not registered: {model_id}") from exc

    def _adapter(self, model: ModelSpec) -> ModelAdapter:
        try:
            return self._adapters[model.id]
        except KeyError as exc:
            raise AIRuntimeError(
                f"Model adapter not registered: {model.id}"
            ) from exc

    @staticmethod
    def _retryable(exc: Exception, fallback: FallbackPolicy | None) -> bool:
        if fallback is None or not fallback.retryable_errors:
            return False
        return exc.__class__.__name__ in fallback.retryable_errors

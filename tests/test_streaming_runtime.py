import tempfile
import unittest
from pathlib import Path

from core.contracts.model_runtime import ModelRequest
from core.contracts.streaming import (
    StreamEvent,
    StreamEventKind,
    StreamCheckpointStatus,
)
from core.execution_state import ExecutionStateStore
from runtime.streaming import StreamingRuntime


class StreamingRuntimeTests(unittest.TestCase):
    def test_consumes_ordered_text_reasoning_and_tool_deltas(self):
        events = [
            StreamEvent(StreamEventKind.TEXT_DELTA, 1, text="hello "),
            StreamEvent(StreamEventKind.REASONING_DELTA, 2, text="think "),
            StreamEvent(
                StreamEventKind.TOOL_CALL_DELTA,
                3,
                call_id="call-1",
                tool_id="echo",
                arguments_delta='{"value":"hel',
            ),
            StreamEvent(
                StreamEventKind.TOOL_CALL_DELTA,
                4,
                call_id="call-1",
                tool_id="echo",
                arguments_delta='lo"}',
            ),
            StreamEvent(StreamEventKind.COMPLETED, 5),
        ]
        result = StreamingRuntime().consume(
            events, model_id="fake", request=ModelRequest("x")
        )
        self.assertEqual(result.response.text, "hello ")
        self.assertEqual(result.result.reasoning, "think ")
        self.assertEqual(
            result.result.tool_calls[0]["arguments"], {"value": "hello"}
        )

    def test_sequence_gap_is_rejected(self):
        with self.assertRaises(ValueError):
            StreamingRuntime().consume(
                [StreamEvent(StreamEventKind.TEXT_DELTA, 2, text="bad")],
                model_id="fake",
                request=ModelRequest("x"),
            )

    def test_stream_must_complete(self):
        with self.assertRaises(RuntimeError):
            StreamingRuntime().consume(
                [StreamEvent(StreamEventKind.TEXT_DELTA, 1, text="partial")],
                model_id="fake",
                request=ModelRequest("x"),
            )

    def test_transient_deltas_are_observed_but_not_journaled(self):
        observed = []
        durable = []
        result = StreamingRuntime(
            observation_sink=observed.append,
            event_sink=durable.append,
        ).consume(
            [
                StreamEvent(StreamEventKind.TEXT_DELTA, 1, text="hello"),
                StreamEvent(StreamEventKind.COMPLETED, 2),
            ],
            model_id="fake",
            request=ModelRequest("x"),
        )
        self.assertEqual([event.kind for event in observed], [
            StreamEventKind.TEXT_DELTA,
            StreamEventKind.COMPLETED,
        ])
        self.assertEqual([event.kind for event in durable], [durable[0].kind])
        self.assertEqual(durable[0].kind.value, "completed")
        self.assertEqual(result.response.text, "hello")

    def test_completed_stream_persists_one_reconstructable_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ExecutionStateStore(Path(temp))
            runtime = StreamingRuntime(execution_state_store=store)
            result = runtime.consume(
                [
                    StreamEvent(StreamEventKind.TEXT_DELTA, 1, text="hello"),
                    StreamEvent(StreamEventKind.REASONING_DELTA, 2, text="think"),
                    StreamEvent(StreamEventKind.COMPLETED, 3),
                ],
                model_id="fake",
                request=ModelRequest("x"),
                work_unit_id="wu-1",
                round_number=2,
                agent_id="agent-1",
            )
            checkpoint = store.load_stream_checkpoint("wu-1")
            self.assertEqual(checkpoint.status, StreamCheckpointStatus.COMPLETED)
            self.assertEqual(checkpoint.text, "hello")
            self.assertEqual(checkpoint.reasoning, "think")
            self.assertEqual(result.checkpoint, checkpoint)
            messages = store.load_messages("wu-1")
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0]["role"], "assistant")
            cursor = store.load_cursor("wu-1")
            self.assertEqual(cursor.round_number, 2)
            self.assertEqual(cursor.conversation_revision, 1)

    def test_resume_reconstructs_completed_state_without_stream_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ExecutionStateStore(Path(temp))
            writer = StreamingRuntime(execution_state_store=store)
            writer.consume(
                [
                    StreamEvent(StreamEventKind.TEXT_DELTA, 1, text="done"),
                    StreamEvent(StreamEventKind.COMPLETED, 2),
                ],
                model_id="fake",
                request=ModelRequest("x"),
                work_unit_id="wu-2",
            )
            resumed = StreamingRuntime(execution_state_store=store).resume("wu-2")
            self.assertEqual(resumed.response.text, "done")
            self.assertEqual(
                resumed.response.metadata["resumed_from_checkpoint"],
                resumed.checkpoint.checkpoint_id,
            )
            self.assertEqual(resumed.result.events, ())

    def test_interrupted_stream_is_not_resumable_as_completed(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ExecutionStateStore(Path(temp))
            runtime = StreamingRuntime(execution_state_store=store)

            def interrupted():
                yield StreamEvent(StreamEventKind.TEXT_DELTA, 1, text="partial")
                raise ConnectionError("provider disconnected")

            with self.assertRaises(ConnectionError):
                runtime.consume(
                    interrupted(),
                    model_id="fake",
                    request=ModelRequest("x"),
                    work_unit_id="wu-3",
                )

            checkpoint = store.load_stream_checkpoint("wu-3")
            self.assertEqual(checkpoint.status, StreamCheckpointStatus.INTERRUPTED)
            with self.assertRaises(RuntimeError):
                runtime.resume("wu-3")

    def test_stream_redacts_sensitive_values_before_observation_and_persistence(self):
        observed = []
        with tempfile.TemporaryDirectory() as temp:
            store = ExecutionStateStore(Path(temp))
            result = StreamingRuntime(
                observation_sink=observed.append,
                execution_state_store=store,
            ).consume(
                [
                    StreamEvent(
                        StreamEventKind.TEXT_DELTA,
                        1,
                        text="token sk-abcdefghijklmnopqrstuvwxyz",
                    ),
                    StreamEvent(StreamEventKind.COMPLETED, 2),
                ],
                model_id="fake",
                request=ModelRequest("x"),
                work_unit_id="wu-4",
            )
            self.assertIn("[REDACTED]", result.response.text)
            self.assertIn("[REDACTED]", observed[0].text)
            checkpoint = store.load_stream_checkpoint("wu-4")
            self.assertIn("[REDACTED]", checkpoint.text)
            self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz", str(
                store.load_messages("wu-4")
            ))


if __name__ == "__main__":
    unittest.main()

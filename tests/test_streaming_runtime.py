import unittest

from core.contracts.model_runtime import ModelRequest
from core.contracts.streaming import StreamEvent, StreamEventKind
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


if __name__ == "__main__":
    unittest.main()

"""Regression tests for path traversal in durable state stores."""

import tempfile
import unittest
from pathlib import Path

from core.execution_state import ExecutionStateStore
from core.state import RuntimeEventStore, SessionStateStore, WorkStateStore
from core.state_paths import state_file_path


class StateStorePathSecurityTests(unittest.TestCase):
    def test_state_file_path_rejects_traversal_and_platform_separators(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "state"
            root.mkdir()
            for identifier in ("../outside", r"..\\outside", "bad:stream", "", ".", "..", "bad\x00id"):
                with self.subTest(identifier=identifier):
                    with self.assertRaisesRegex(ValueError, "invalid state identifier"):
                        state_file_path(root, identifier, ".json")

    def test_state_file_path_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "state"
            root.mkdir()
            outside = Path(temp) / "outside.json"
            outside.write_text("safe", encoding="utf-8")
            try:
                (root / "session-1.json").symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable in this environment")

            with self.assertRaisesRegex(ValueError, "state path escapes configured root"):
                state_file_path(root, "session-1", ".json")
            self.assertEqual(outside.read_text(encoding="utf-8"), "safe")

    def test_state_stores_reject_traversal_identifiers_on_load(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work = WorkStateStore(root / "work")
            execution = ExecutionStateStore(root / "execution")
            events = RuntimeEventStore(root / "events")
            sessions = SessionStateStore(root / "sessions")

            checks = (
                lambda: work.load("../outside"),
                lambda: work.exists("../outside"),
                lambda: work.load_checkpoint("../outside"),
                lambda: execution.load_cursor("../outside"),
                lambda: execution.load_messages("../outside"),
                lambda: execution.load_stream_checkpoint("../outside"),
                lambda: events.load("../outside"),
                lambda: events.next_sequence("../outside"),
                lambda: sessions.exists("../outside"),
                lambda: sessions.load("../outside"),
            )
            for check in checks:
                with self.subTest(check=check):
                    with self.assertRaisesRegex(ValueError, "invalid state identifier"):
                        check()


if __name__ == "__main__":
    unittest.main()

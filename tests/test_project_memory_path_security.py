"""Regression tests for symlink escapes in the project memory journal."""

import tempfile
import unittest
from pathlib import Path

from core.memory import ProjectMemoryStore


class ProjectMemoryPathSecurityTests(unittest.TestCase):
    def test_search_and_append_reject_symlinked_memory_journal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store_root = root / "memory"
            store_root.mkdir()
            outside = root / "outside.jsonl"
            sentinel = '{"memory_id":"outside","kind":"note","content":"do not read or modify","source":"test","created_at":"2026-01-01T00:00:00+00:00","metadata":{}}\n'
            outside.write_text(sentinel, encoding="utf-8")
            try:
                (store_root / "memory.jsonl").symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable in this environment")

            store = ProjectMemoryStore(store_root)
            with self.assertRaisesRegex(ValueError, "state path escapes configured root"):
                store.search()
            with self.assertRaisesRegex(ValueError, "state path escapes configured root"):
                store.append("must not be written outside the store")
            self.assertEqual(outside.read_text(encoding="utf-8"), sentinel)


if __name__ == "__main__":
    unittest.main()

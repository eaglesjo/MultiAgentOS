import tempfile
import unittest
from pathlib import Path

from core.contracts.memory import MemoryKind
from core.memory import ProjectMemoryStore


class ProjectMemoryStoreTests(unittest.TestCase):
    def test_append_and_search_are_durable_and_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectMemoryStore(Path(temp) / "memory")
            first = store.append("Use the project runtime for execution", kind=MemoryKind.DECISION, source="agent")
            store.append("React Native is the project stack", kind=MemoryKind.FACT, source="inspect")
            store.append("Keep changes small", kind=MemoryKind.PREFERENCE, source="user")
            result = store.search("project", limit=2)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0].memory_id, first.memory_id)

    def test_sensitive_values_are_redacted_before_persistence(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectMemoryStore(Path(temp) / "memory")
            memory = store.append(
                "credential is sk-abcdefghijklmnopqrstuvwxyz",
                metadata={"api_key": "secret-value"},
            )
            raw = (Path(temp) / "memory" / "memory.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz", raw)
            self.assertNotIn("secret-value", raw)
            self.assertIn("[REDACTED]", memory.content)
            self.assertEqual(memory.metadata["api_key"], "[REDACTED]")


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from runtime.execution_config import (
    DEFAULT_EXECUTION_CONFIG,
    load_execution_config,
    write_default_execution_config,
)


class ExecutionConfigTests(unittest.TestCase):
    def test_default_config_is_written_and_loaded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = write_default_execution_config(root)
            self.assertEqual(path, root / ".multiagentos" / "execution.json")
            self.assertEqual(load_execution_config(root), DEFAULT_EXECUTION_CONFIG)

    def test_existing_config_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / ".multiagentos"
            target.mkdir()
            (target / "execution.json").write_text(
                json.dumps({
                    "version": 1,
                    "runtime": "process",
                    "agent_id": "custom-executor",
                    "model_id": "custom-process",
                }),
                encoding="utf-8",
            )
            write_default_execution_config(root)
            config = load_execution_config(root)
            self.assertEqual(config.agent_id, "custom-executor")
            self.assertEqual(config.model_id, "custom-process")

    def test_invalid_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / ".multiagentos"
            target.mkdir()
            (target / "execution.json").write_text(
                json.dumps({
                    "version": 99,
                    "runtime": "process",
                    "agent_id": "cli-executor",
                    "model_id": "local-process",
                }),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_execution_config(root)

    def test_missing_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):
                load_execution_config(Path(temp))

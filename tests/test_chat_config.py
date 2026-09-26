import tempfile
import unittest
from pathlib import Path

from runtime.chat_config import DEFAULT_CHAT_CONFIG, load_chat_config, write_default_chat_config


class ChatConfigTests(unittest.TestCase):
    def test_default_chat_config_is_chatgpt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_default_chat_config(root)
            self.assertEqual(load_chat_config(root), DEFAULT_CHAT_CONFIG)

    def test_custom_chat_agent_and_model_are_loaded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / ".multiagentos"
            target.mkdir()
            (target / "chat.json").write_text(
                '{"version": 1, "agent_id": "gemini", "model": "gemini-model"}',
                encoding="utf-8",
            )
            config = load_chat_config(root)
            self.assertEqual(config.agent_id, "gemini")
            self.assertEqual(config.model, "gemini-model")

    def test_missing_chat_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):
                load_chat_config(Path(temp))

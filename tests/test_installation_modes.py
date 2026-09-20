import json
import tempfile
import unittest
from pathlib import Path

from installer.components import (
    ALL,
    MULTI_AGENT,
    VYRELON,
    resolve_installation,
)
from installer.init import ProjectInitializer


class TestInstallationModes(unittest.TestCase):
    def test_vyrelon_only(self):
        installation = resolve_installation(VYRELON)
        self.assertEqual(installation.components, frozenset({VYRELON}))
        self.assertTrue(installation.has_vyrelon)
        self.assertFalse(installation.has_multi_agent)

    def test_multi_agent_only(self):
        installation = resolve_installation(MULTI_AGENT)
        self.assertFalse(installation.has_vyrelon)
        self.assertTrue(installation.has_multi_agent)

    def test_all(self):
        installation = resolve_installation(ALL)
        self.assertTrue(installation.has_vyrelon)
        self.assertTrue(installation.has_multi_agent)

    def test_initializer_can_install_vyrelon_without_agent_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = ProjectInitializer().apply(
                root, (), component=VYRELON
            )
            self.assertTrue(config.exists())
            self.assertFalse((root / ".multiagentos" / "agents.json").exists())
            payload = json.loads(
                (root / ".multiagentos" / "components.json").read_text()
            )
            self.assertEqual(payload["components"], [VYRELON])

    def test_initializer_can_install_multi_agent_layer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ProjectInitializer().apply(root, (), component=MULTI_AGENT)
            self.assertTrue((root / ".multiagentos" / "agents.json").exists())
            payload = json.loads(
                (root / ".multiagentos" / "components.json").read_text()
            )
            self.assertEqual(payload["components"], [MULTI_AGENT])


if __name__ == "__main__":
    unittest.main()

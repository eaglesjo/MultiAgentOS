import json
import unittest
from pathlib import Path


class AgentPluginPackageTests(unittest.TestCase):
    def test_manifest_and_skill_layout(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["$schema"],
            "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        )
        self.assertEqual(manifest["name"], "multiagentos")
        skill = root / "skills" / "multiagentos-runtime" / "SKILL.md"
        self.assertTrue(skill.is_file())
        self.assertTrue(skill.read_text(encoding="utf-8").startswith("---\nname: multiagentos-runtime\n"))


if __name__ == "__main__":
    unittest.main()

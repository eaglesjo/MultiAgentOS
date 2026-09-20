import json
import tempfile
import unittest
from pathlib import Path

from installer.init import ProjectInitializer
from profiles.detector import ProfileDetector


class ProfileInstallerTests(unittest.TestCase):
    def test_detects_react_native(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(
                json.dumps({"dependencies": {"react-native": "0.82.0"}}),
                encoding="utf-8",
            )
            results = ProfileDetector().detect(root)
            self.assertEqual(results[0].profile_id, "react-native")

    def test_initializer_writes_profile_config(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            detections = ProfileDetector().detect(root)
            path = ProjectInitializer().apply(root, detections)
            self.assertTrue(path.exists())
            self.assertEqual(json.loads(path.read_text())["version"], 1)


if __name__ == "__main__":
    unittest.main()

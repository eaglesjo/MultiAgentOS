import json
import tempfile
import unittest
from pathlib import Path

from multiagentos.cli import main


class CLITests(unittest.TestCase):
    def test_detect(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(
                json.dumps({"dependencies": {"react-native": "0.82.0"}}),
                encoding="utf-8",
            )
            self.assertEqual(main(["detect", str(root)]), 0)

    def test_init(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(main(["init", temp]), 0)
            self.assertTrue((Path(temp) / ".multiagentos" / "profile.json").exists())


if __name__ == "__main__":
    unittest.main()

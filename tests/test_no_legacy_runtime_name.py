"""Repository invariant: the retired runtime brand must not remain in source or docs."""

from pathlib import Path
import unittest


class NoLegacyRuntimeNameTests(unittest.TestCase):
    def test_retired_runtime_name_is_absent_from_repository(self):
        root = Path(__file__).resolve().parents[1]
        legacy_upper = "VY" + "RELON"
        legacy_lower = "vy" + "relon"
        legacy_title = "Vy" + "relon"

        ignored_dirs = {".git", "__pycache__", "node_modules", "build", "dist", ".pytest_cache"}
        # Ignore virtual environments by prefix while still scanning repository source/docs.
        ignored_dir_prefixes = (".venv", "venv")
        offenders = []

        for path in root.rglob("*"):
            if not path.is_file() or any(part in ignored_dirs or part.startswith(ignored_dir_prefixes) for part in path.parts):
                continue
            try:
                source = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if legacy_upper in source or legacy_lower in source or legacy_title in source:
                offenders.append(str(path.relative_to(root)))

        self.assertEqual(offenders, [], f"retired runtime name remains in: {offenders}")


if __name__ == "__main__":
    unittest.main()

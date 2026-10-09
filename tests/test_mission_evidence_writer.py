import json
import tempfile
import unittest
from pathlib import Path

from scripts.write_mission_evidence import build_evidence, write_evidence


class MissionEvidenceWriterTests(unittest.TestCase):
    def test_mission_id_is_encoded_as_json_not_interpolated(self):
        mission_id = 'mission-"quoted"\nsecond-line'
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "mission-evidence" / "result.json"
            write_evidence(
                target,
                mission_id=mission_id,
                source_sha="a" * 40,
                operation="test",
                run_id="12345",
            )
            loaded = json.loads(target.read_text(encoding="utf-8"))

        self.assertEqual(loaded["mission_id"], mission_id)
        self.assertEqual(loaded["source_sha"], "a" * 40)
        self.assertEqual(loaded["run_id"], 12345)
        self.assertEqual(loaded["status"], "completed")
        self.assertEqual(loaded["conclusion"], "success")

    def test_invalid_source_sha_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "source_sha"):
            build_evidence(
                mission_id="mission-1",
                source_sha="not-a-commit",
                operation="test",
                run_id=123,
            )

    def test_unbounded_operation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported operation"):
            build_evidence(
                mission_id="mission-1",
                source_sha="a" * 40,
                operation="shell",
                run_id=123,
            )

    def test_empty_mission_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "mission_id"):
            build_evidence(
                mission_id="  ",
                source_sha="a" * 40,
                operation="verify",
                run_id=123,
            )


if __name__ == "__main__":
    unittest.main()

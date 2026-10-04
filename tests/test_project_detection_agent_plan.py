import json
import tempfile
import unittest
from pathlib import Path

from profiles.agent_plan import build_agent_plan
from profiles.detector import ProfileDetector


class ProjectDetectionAgentPlanTests(unittest.TestCase):
    def test_android_selects_only_android_specialists(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "settings.gradle").write_text("rootProject.name='app'\n", encoding="utf-8")
            (root / "build.gradle").write_text(
                "plugins { id 'com.android.application' version '8.0.0' apply false }\n",
                encoding="utf-8",
            )
            detections = ProfileDetector().detect(root)
            self.assertEqual(detections[0].profile_id, "android-native")
            self.assertGreaterEqual(detections[0].confidence, 0.9)

            plan = build_agent_plan(root, detections)
            self.assertIn("android-architect", plan.selected)
            self.assertIn("kotlin-developer", plan.selected)
            self.assertIn("gradle", plan.selected)
            self.assertNotIn("react-developer", plan.selected)
            self.assertNotIn("swift-developer", plan.selected)
            self.assertFalse(plan.requires_approval)

    def test_react_native_does_not_activate_native_platform_specialists(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(
                json.dumps({"dependencies": {"react-native": "0.80.0"}}),
                encoding="utf-8",
            )
            detections = ProfileDetector().detect(root)
            self.assertEqual(detections[0].profile_id, "react-native")
            plan = build_agent_plan(root, detections)
            self.assertIn("react-native-developer", plan.selected)
            self.assertIn("ui-react-native", plan.selected)
            self.assertNotIn("android-developer", plan.selected)
            self.assertNotIn("ios-developer", plan.selected)

    def test_empty_project_requires_approval_and_has_governance_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            detections = ProfileDetector().detect(root)
            plan = build_agent_plan(root, detections)
            self.assertEqual(detections, ())
            self.assertTrue(plan.requires_approval)
            self.assertEqual(plan.profiles, ())
            self.assertIn("planner", plan.selected)
            self.assertIn("executor", plan.selected)


if __name__ == "__main__":
    unittest.main()

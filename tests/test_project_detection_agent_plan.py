import json
import tempfile
import unittest
from pathlib import Path

from installer.init import ProjectInitializer
from profiles.agent_plan import build_agent_plan
from profiles.detector import ProfileDetector


class ProjectDetectionAgentPlanTests(unittest.TestCase):
    def test_android_requires_independent_evidence_for_automatic_activation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "settings.gradle").write_text("rootProject.name='app'\n", encoding="utf-8")
            detections = ProfileDetector().detect(root)
            self.assertEqual(detections[0].profile_id, "android-native")
            self.assertEqual(detections[0].confidence, 0.35)
            self.assertTrue(build_agent_plan(root, detections).requires_approval)

    def test_android_strong_evidence_activates_only_android_specialists(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "settings.gradle").write_text("rootProject.name='app'\n", encoding="utf-8")
            (root / "build.gradle").write_text(
                "plugins { id 'com.android.application' version '8.0.0' apply false }\n",
                encoding="utf-8",
            )
            detections = ProfileDetector().detect(root)
            self.assertEqual(detections[0].profile_id, "android-native")
            self.assertEqual(detections[0].confidence, 1.0)

            plan = build_agent_plan(root, detections)
            self.assertIn("android-architect", plan.selected)
            self.assertIn("kotlin-developer", plan.selected)
            self.assertIn("gradle", plan.selected)
            self.assertNotIn("react-developer", plan.selected)
            self.assertNotIn("swift-developer", plan.selected)
            self.assertFalse(plan.requires_approval)

    def test_react_native_is_high_confidence_from_dependency_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(
                json.dumps({"dependencies": {"react-native": "0.80.0"}}),
                encoding="utf-8",
            )
            detections = ProfileDetector().detect(root)
            self.assertEqual(detections[0].profile_id, "react-native")
            self.assertEqual(detections[0].confidence, 1.0)
            plan = build_agent_plan(root, detections)
            self.assertIn("react-native-developer", plan.selected)
            self.assertIn("ui-react-native", plan.selected)
            self.assertNotIn("android-developer", plan.selected)
            self.assertNotIn("ios-developer", plan.selected)

    def test_ios_project_uses_xcode_structure_as_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Sample.xcodeproj").mkdir()
            (root / "Sources").mkdir()
            (root / "Sources" / "App.swift").write_text("import SwiftUI\n", encoding="utf-8")
            detections = ProfileDetector().detect(root)
            self.assertEqual(detections[0].profile_id, "ios-native")
            self.assertEqual(detections[0].confidence, 1.0)
            self.assertFalse(build_agent_plan(root, detections).requires_approval)

    def test_react_native_platform_ambiguity_requires_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(
                json.dumps({"dependencies": {"react-native": "0.80.0"}}),
                encoding="utf-8",
            )
            detections = ProfileDetector().detect(root)
            plan = build_agent_plan(root, detections)
            self.assertTrue(plan.requires_approval)
            self.assertIsNotNone(plan.classification)
            self.assertIn("React Native detected without an explicit native platform", plan.rationale)

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

    def test_initializer_blocks_low_confidence_without_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "settings.gradle").write_text("rootProject.name='app'\n", encoding="utf-8")
            detections = ProfileDetector().detect(root)
            with self.assertRaises(PermissionError):
                ProjectInitializer().apply(root, detections)
            ProjectInitializer().apply(root, detections, approved=True)
            self.assertTrue((root / ".multiagentos" / "profile.json").exists())


if __name__ == "__main__":
    unittest.main()

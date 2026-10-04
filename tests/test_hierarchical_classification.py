import tempfile
import unittest
from pathlib import Path

from profiles.classifier import classify_project
from profiles.detector import ProfileDetector


class HierarchicalClassificationTests(unittest.TestCase):
    def test_android_is_classified_hierarchically(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "settings.gradle").write_text("rootProject.name='app'\n", encoding="utf-8")
            (root / "build.gradle").write_text(
                "plugins { id 'com.android.application' version '8.0.0' apply false }\n",
                encoding="utf-8",
            )
            classification = classify_project(ProfileDetector().detect(root))
            self.assertEqual(classification.platform.values, ("Android",))
            self.assertEqual(classification.framework_runtime.values, ("Android Native",))
            self.assertIn("Gradle", classification.language_toolchain.values)
            self.assertIn("Kotlin", classification.language_toolchain.values)
            self.assertFalse(classification.ambiguous)
            self.assertFalse(classification.requires_approval)

    def test_ios_is_classified_hierarchically(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "App.xcodeproj").mkdir()
            (root / "App.swift").write_text("import SwiftUI\n", encoding="utf-8")
            classification = classify_project(ProfileDetector().detect(root))
            self.assertEqual(classification.platform.values, ("iOS",))
            self.assertEqual(classification.framework_runtime.values, ("iOS Native",))
            self.assertIn("Xcode", classification.language_toolchain.values)
            self.assertIn("Swift", classification.language_toolchain.values)
            self.assertFalse(classification.requires_approval)

    def test_react_native_without_native_platform_is_explicitly_ambiguous(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(
                '{"dependencies":{"react-native":"0.80.0"}}',
                encoding="utf-8",
            )
            classification = classify_project(ProfileDetector().detect(root))
            self.assertEqual(classification.platform.values, ())
            self.assertEqual(classification.framework_runtime.values, ("React Native",))
            self.assertTrue(classification.ambiguous)
            self.assertTrue(classification.requires_approval)

    def test_multiple_native_platforms_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "settings.gradle").write_text("rootProject.name='app'\n", encoding="utf-8")
            (root / "build.gradle").write_text(
                "plugins { id 'com.android.application' version '8.0.0' apply false }\n",
                encoding="utf-8",
            )
            (root / "App.xcodeproj").mkdir()
            (root / "App.swift").write_text("import SwiftUI\n", encoding="utf-8")
            classification = classify_project(ProfileDetector().detect(root))
            self.assertEqual(set(classification.platform.values), {"Android", "iOS"})
            self.assertTrue(classification.ambiguous)
            self.assertTrue(classification.requires_approval)


if __name__ == "__main__":
    unittest.main()

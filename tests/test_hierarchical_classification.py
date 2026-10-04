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
            self.assertNotIn("Java", classification.language_toolchain.values)
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

    def test_android_does_not_infer_languages_without_source_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "settings.gradle").write_text("rootProject.name='app'\n", encoding="utf-8")
            (root / "build.gradle").write_text(
                "plugins { id 'com.android.application' version '8.0.0' apply false }\n",
                encoding="utf-8",
            )
            classification = classify_project(ProfileDetector().detect(root))
            self.assertNotIn("Kotlin", classification.language_toolchain.values)
            self.assertNotIn("Java", classification.language_toolchain.values)
            self.assertIn("Gradle", classification.language_toolchain.values)

    def test_ios_does_not_infer_spm_without_package_swift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "App.xcodeproj").mkdir()
            (root / "App.swift").write_text("import SwiftUI\n", encoding="utf-8")
            classification = classify_project(ProfileDetector().detect(root))
            self.assertIn("Xcode", classification.language_toolchain.values)
            self.assertNotIn("Swift Package Manager", classification.language_toolchain.values)
            self.assertIn("Swift", classification.language_toolchain.values)

    def test_react_native_language_is_evidence_driven(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(
                '{"dependencies":{"react-native":"0.80.0"}}',
                encoding="utf-8",
            )
            (root / "App.tsx").write_text("export default function App() {}\n", encoding="utf-8")
            classification = classify_project(ProfileDetector().detect(root))
            self.assertIn("React Native", classification.framework_runtime.values)
            self.assertIn("Node.js", classification.language_toolchain.values)
            self.assertIn("TypeScript", classification.language_toolchain.values)
            self.assertNotIn("JavaScript", classification.language_toolchain.values)


if __name__ == "__main__":
    unittest.main()

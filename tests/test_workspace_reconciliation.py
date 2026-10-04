import json
import tempfile
import unittest
from pathlib import Path

from profiles.agent_plan import build_agent_plan
from profiles.reconciliation import apply_reconciliation, build_reconciliation
from profiles.workspace import aggregate_detections, analyze_workspaces, discover_workspaces


class WorkspaceDetectionTests(unittest.TestCase):
    def test_npm_workspaces_are_detected_independently(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(
                json.dumps({"workspaces": ["apps/*"]}), encoding="utf-8"
            )
            android = root / "apps" / "android"
            web = root / "apps" / "web"
            android.mkdir(parents=True)
            web.mkdir(parents=True)
            (android / "package.json").write_text("{}\n", encoding="utf-8")
            (android / "settings.gradle").write_text("include ':app'\n", encoding="utf-8")
            (web / "package.json").write_text(
                json.dumps({"dependencies": {"react-native": "0.80.0"}}), encoding="utf-8"
            )
            self.assertEqual(
                {spec.id for spec in discover_workspaces(root)},
                {"root", "apps/android", "apps/web"},
            )

    def test_gradle_subprojects_become_workspaces(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "settings.gradle").write_text(
                "include(':app', ':core:network')\n", encoding="utf-8"
            )
            (root / "app").mkdir()
            (root / "core" / "network").mkdir(parents=True)
            self.assertEqual(
                {spec.id for spec in discover_workspaces(root)},
                {"root", "app", "core/network"},
            )

    def test_android_and_react_native_workspace_plans_are_union_without_cross_contamination(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(
                json.dumps({"workspaces": ["apps/*"]}), encoding="utf-8"
            )
            android = root / "apps" / "android"
            web = root / "apps" / "web"
            android.mkdir(parents=True)
            web.mkdir(parents=True)
            (android / "package.json").write_text("{}\n", encoding="utf-8")
            (android / "settings.gradle").write_text("rootProject.name='android'\n", encoding="utf-8")
            (android / "build.gradle").write_text(
                "plugins { id 'com.android.application' version '8.0.0' apply false }\n",
                encoding="utf-8",
            )
            (android / "MainActivity.kt").write_text("class MainActivity {}\n", encoding="utf-8")
            (web / "package.json").write_text(
                json.dumps({"dependencies": {"react-native": "0.80.0"}}), encoding="utf-8"
            )
            (web / "App.tsx").write_text(
                "export default function App() {}\n", encoding="utf-8"
            )

            analyses = analyze_workspaces(root)
            plan = build_agent_plan(root, aggregate_detections(analyses))
            self.assertIn("android-developer", plan.selected)
            self.assertIn("react-native-developer", plan.selected)
            self.assertNotIn("ios-developer", plan.selected)
            self.assertEqual(
                next(a for a in analyses if a.spec.id == "apps/android").detections[0].profile_id,
                "android-native",
            )
            self.assertEqual(
                next(a for a in analyses if a.spec.id == "apps/web").detections[0].profile_id,
                "react-native",
            )

    def test_reconciliation_adds_and_removes_agents(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / ".multiagentos"
            target.mkdir()
            (target / "agents.json").write_text(
                json.dumps({"version": 1, "agents": [
                    {"id": "android-developer"}, {"id": "planner"}
                ]}), encoding="utf-8"
            )
            analyses = analyze_workspaces(root)
            plan = build_agent_plan(root, ())
            reconciliation = build_reconciliation(root, plan, analyses)
            self.assertIn("android-developer", reconciliation.to_remove)
            self.assertIn("planner", reconciliation.unchanged)
            self.assertIn("executor", reconciliation.to_add)

    def test_reconciliation_blocks_ambiguous_plan_without_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(
                json.dumps({"dependencies": {"react-native": "0.80.0"}}),
                encoding="utf-8",
            )
            analyses = analyze_workspaces(root)
            plan = build_agent_plan(root, aggregate_detections(analyses))
            with self.assertRaises(PermissionError):
                apply_reconciliation(root, plan, analyses)
            result = apply_reconciliation(root, plan, analyses, approved=True)
            self.assertTrue((root / ".multiagentos" / "reconciliation.json").exists())
            self.assertIn("planner", result.desired)


if __name__ == "__main__":
    unittest.main()

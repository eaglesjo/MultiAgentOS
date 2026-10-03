import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts" / "macos"


class TunnelLaunchdScriptTests(unittest.TestCase):
    def test_project_scoped_scripts_are_valid_bash(self):
        for name in (
            "install_tunnel_client_launchd.sh",
            "status_tunnel_client_launchd.sh",
            "uninstall_tunnel_client_launchd.sh",
        ):
            with self.subTest(script=name):
                result = subprocess.run(
                    ["bash", "-n", str(SCRIPTS / name)],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_scripts_use_project_scoped_tunnel_identity(self):
        install = (SCRIPTS / "install_tunnel_client_launchd.sh").read_text()
        status = (SCRIPTS / "status_tunnel_client_launchd.sh").read_text()
        uninstall = (SCRIPTS / "uninstall_tunnel_client_launchd.sh").read_text()

        for content in (install, status, uninstall):
            self.assertIn("multiagentos.tunnel.project.", content)
            self.assertIn("sha256", content)
            self.assertIn("--path", content)

        self.assertNotIn("com.eaglesjo.multiagentos.tunnel-client", install)
        self.assertNotIn("com.eaglesjo.multiagentos.tunnel-client", status)
        self.assertNotIn("com.eaglesjo.multiagentos.tunnel-client", uninstall)

    def test_install_has_project_specific_keychain_and_health_address(self):
        install = (SCRIPTS / "install_tunnel_client_launchd.sh").read_text()
        self.assertIn(
            'keychain = f"multiagentos.tunnel.project.{project_id}.runtime-key"',
            install,
        )
        self.assertIn('KEYCHAIN_SERVICE=""', install)
        self.assertIn("HEALTH_LISTEN_ADDR", install)
        self.assertIn("MAOS_HEALTH_LISTEN_ADDR", install)


if __name__ == "__main__":
    unittest.main()

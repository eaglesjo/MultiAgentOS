import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "macos"
    / "install_tunnel_client_launchd.sh"
)


class TunnelInstallerScriptTests(unittest.TestCase):
    def setUp(self):
        self.script = SCRIPT.read_text()

    def test_accepts_arbitrary_existing_project_roots(self):
        self.assertNotIn('pyproject.toml', self.script)
        self.assertIn('if [[ ! -d "$PROJECT_ROOT" ]]; then', self.script)
        self.assertIn('echo "ERROR: project root not found: $PROJECT_ROOT"', self.script)

    def test_waits_for_previous_launchd_service_before_bootstrap(self):
        stop = self.script.index('launchctl bootout')
        wait = self.script.index('echo "== Wait for previous project tunnel service to unload =="')
        bootstrap = self.script.index('launchctl bootstrap')

        self.assertLess(stop, wait)
        self.assertLess(wait, bootstrap)
        self.assertIn(
            'if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then',
            self.script,
        )
        self.assertIn(
            'echo "ERROR: previous tunnel service did not unload: $LABEL"',
            self.script,
        )

    def test_documents_plain_mcp_server_url(self):
        self.assertIn(
            'MCP_SERVER_URL       Exact project MCP endpoint, e.g. http://127.0.0.1:8003/mcp',
            self.script,
        )
        self.assertNotIn('[http://127.0.0.1:8003/mcp]', self.script)


if __name__ == "__main__":
    unittest.main()

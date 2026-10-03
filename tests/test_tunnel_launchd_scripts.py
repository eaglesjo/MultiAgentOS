import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class TunnelLaunchdScriptTests(unittest.TestCase):
    def test_install_requires_explicit_project_endpoints(self):
        t=(ROOT/"scripts/macos/install_tunnel_client_launchd.sh").read_text()
        self.assertIn("--mcp-server-url",t)
        self.assertIn("--health-listen-addr",t)
        self.assertIn('MCP_SERVER_URL="${MCP_SERVER_URL:-}"',t)
        self.assertIn('HEALTH_LISTEN_ADDR="${HEALTH_LISTEN_ADDR:-}"',t)
        self.assertNotIn("127.0.0.1:8000/mcp",t)
    def test_install_waits_for_unload(self):
        t=(ROOT/"scripts/macos/install_tunnel_client_launchd.sh").read_text()
        self.assertIn("launchctl bootout",t); self.assertIn("launchctl print",t); self.assertIn("launchctl bootstrap",t)
    def test_uninstall_is_project_scoped(self):
        t=(ROOT/"scripts/macos/uninstall_tunnel_client_launchd.sh").read_text()
        self.assertIn("--path",t); self.assertIn("multiagentos.tunnel.project.$PROJECT_ID",t); self.assertIn("launchctl print",t)
    def test_status_is_project_scoped(self):
        t=(ROOT/"scripts/macos/status_tunnel_client_launchd.sh").read_text()
        self.assertIn("--path",t); self.assertIn("multiagentos.tunnel.project.$PROJECT_ID",t)
if __name__=="__main__": unittest.main()

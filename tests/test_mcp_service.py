import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from multiagentos.cli import build_parser
from multiagentos.mcp_service import LABEL, install_mcp_service


class MCPServiceTests(unittest.TestCase):
    def test_cli_exposes_install_uninstall_status(self):
        install = build_parser().parse_args(
            ["mcp", "install", "--path", "/tmp/project", "--allow-write"]
        )
        self.assertEqual(install.mcp_command, "install")
        self.assertTrue(install.allow_write)
        self.assertFalse(install.allow_process)

        uninstall = build_parser().parse_args(["mcp", "uninstall"])
        self.assertEqual(uninstall.mcp_command, "uninstall")

        status = build_parser().parse_args(["mcp", "status"])
        self.assertEqual(status.mcp_command, "status")

    @patch("multiagentos.mcp_service._launchctl")
    @patch("multiagentos.mcp_service.shutil.which", return_value="/usr/local/bin/multiagentos")
    def test_install_writes_keepalive_launch_agent(self, which, launchctl):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("multiagentos.mcp_service.PLIST_PATH", root / "service.plist"):
                with patch("multiagentos.mcp_service.LAUNCH_AGENTS_DIR", root / "LaunchAgents"):
                    with patch.object(sys, "platform", "darwin"):
                        message = install_mcp_service(
                            root,
                            allow_write=True,
                            allow_process=False,
                        )

            self.assertIn("installed and started", message)
            plist = plistlib.loads((root / "service.plist").read_bytes())
            self.assertEqual(plist["Label"], LABEL)
            self.assertTrue(plist["RunAtLoad"])
            self.assertTrue(plist["KeepAlive"])
            self.assertIn("--allow-write", plist["ProgramArguments"])
            self.assertNotIn("--allow-process", plist["ProgramArguments"])


if __name__ == "__main__":
    unittest.main()

import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from multiagentos.cli import build_parser
from multiagentos.mcp_service import (
    LABEL,
    WINDOWS_TASK_NAME,
    _windows_task_xml,
    install_mcp_service,
    mcp_service_status,
    uninstall_mcp_service,
)


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

    @patch("multiagentos.mcp_service._wait_for_endpoint", return_value=True)
    @patch("multiagentos.mcp_service._schtasks")
    def test_install_creates_and_runs_windows_task_without_visible_console(self, schtasks, wait_for_endpoint):
        schtasks.return_value.returncode = 0
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(sys, "platform", "win32"):
                with patch.object(sys, "executable", r"C:\Python314\python.exe"):
                    with patch("multiagentos.mcp_service.Path.is_file", return_value=True):
                        with patch.dict(
                        "os.environ",
                            {"USERDOMAIN": "HJKOO-PC", "USERNAME": "eaglesjo"},
                            clear=False,
                        ):
                            message = install_mcp_service(
                                root,
                                allow_write=True,
                                allow_process=False,
                            )

        self.assertIn("Task Scheduler will start it at user logon", message)
        create_call = schtasks.call_args_list[0]
        self.assertEqual(create_call.args[0], "/Create")
        self.assertIn(WINDOWS_TASK_NAME, create_call.args)
        self.assertIn("/XML", create_call.args)
        xml_path = create_call.args[create_call.args.index("/XML") + 1]
        self.assertFalse(Path(xml_path).exists())
        self.assertIn("/F", create_call.args)

        xml = _windows_task_xml(
            [r"C:\Python314\pythonw.exe", "-m", "multiagentos.cli", "mcp", "serve-http",
             "--path", str(root), "--host", "127.0.0.1", "--port", "8000", "--allow-write"],
            project_root=root,
        )
        self.assertIn("<LogonType>InteractiveToken</LogonType>", xml)
        self.assertIn("<RunLevel>LeastPrivilege</RunLevel>", xml)
        self.assertIn("<AllowStartOnDemand>true</AllowStartOnDemand>", xml)
        self.assertIn("<StartWhenAvailable>true</StartWhenAvailable>", xml)
        self.assertIn("<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>", xml)
        self.assertIn("<WorkingDirectory>", xml)
        self.assertIn(r"C:\Python314\pythonw.exe", xml)
        self.assertIn("--allow-write", xml)

        run_call = schtasks.call_args_list[1]
        self.assertEqual(run_call.args[0], "/Run")
        self.assertIn(WINDOWS_TASK_NAME, run_call.args)

        wait_for_endpoint.assert_called_once_with("127.0.0.1", 8000)

    @patch("multiagentos.mcp_service._schtasks")
    def test_windows_status_and_uninstall(self, schtasks):
        schtasks.return_value.returncode = 0
        schtasks.return_value.stdout = "TaskName: \\MultiAgentOS Local MCP\nStatus: Running\n"
        with patch.object(sys, "platform", "win32"):
            status = mcp_service_status()
            message = uninstall_mcp_service()

        self.assertIn("Status: Running", status)
        self.assertIn("removed", message)
        self.assertEqual(schtasks.call_args_list[0].args[0], "/Query")
        self.assertEqual(schtasks.call_args_list[1].args[0], "/End")
        self.assertEqual(schtasks.call_args_list[2].args[0], "/Delete")


if __name__ == "__main__":
    unittest.main()

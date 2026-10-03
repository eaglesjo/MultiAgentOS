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
    _service_label,
    _windows_task_name,
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

    @unittest.skipUnless(sys.platform == "darwin", "macOS launchd test")
    @patch("multiagentos.mcp_service._wait_for_endpoint", return_value=True)
    @patch("multiagentos.mcp_service._launchctl")
    @patch("multiagentos.mcp_service.shutil.which", return_value="/usr/local/bin/multiagentos")
    def test_install_writes_keepalive_launch_agent(self, which, launchctl, endpoint):
        def launchctl_side_effect(*args, **kwargs):
            from subprocess import CompletedProcess
            if args[0] == "bootstrap":
                return CompletedProcess(args, 0, "", "")
            if args[0] == "kickstart":
                return CompletedProcess(args, 0, "", "")
            return CompletedProcess(args, 1, "", "")
        launchctl.side_effect = launchctl_side_effect
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("multiagentos.mcp_service.LAUNCH_AGENTS_DIR", root / "LaunchAgents"):
                with patch.object(sys, "platform", "darwin"):
                    message = install_mcp_service(
                        root,
                        allow_write=True,
                        allow_process=False,
                    )

            self.assertIn("installed and started", message)
            plist_path = next((root / "LaunchAgents").glob("*.plist"))
            plist = plistlib.loads(plist_path.read_bytes())
            self.assertEqual(plist["Label"], _service_label(root))
            self.assertTrue(plist["RunAtLoad"])
            self.assertTrue(plist["KeepAlive"])
            self.assertIn("--allow-write", plist["ProgramArguments"])
            self.assertNotIn("--allow-process", plist["ProgramArguments"])

    @unittest.skipUnless(sys.platform == "win32", "Windows Task Scheduler test")
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
        create_call = next(call for call in schtasks.call_args_list if call.args[0] == "/Create")
        self.assertEqual(create_call.args[0], "/Create")
        self.assertIn(_windows_task_name(root), create_call.args)
        self.assertIn("/XML", create_call.args)
        xml_path = create_call.args[create_call.args.index("/XML") + 1]
        self.assertFalse(Path(xml_path).exists())
        self.assertIn("/F", create_call.args)

        xml = _windows_task_xml(
            [r"C:\Python314\pythonw.exe", "-m", "multiagentos.windows_launcher",
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

        run_call = next(call for call in schtasks.call_args_list if call.args[0] == "/Run")
        self.assertEqual(run_call.args[0], "/Run")
        self.assertIn(_windows_task_name(root), run_call.args)

        wait_for_endpoint.assert_called_once_with("127.0.0.1", 8000)

    @unittest.skipUnless(sys.platform == "win32", "Windows Task Scheduler test")
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
        self.assertIn("/End", [call.args[0] for call in schtasks.call_args_list])
        self.assertIn("/Delete", [call.args[0] for call in schtasks.call_args_list])

    def test_project_services_have_distinct_service_ids(self):
        first = Path("/tmp/project-one").resolve()
        second = Path("/tmp/project-two").resolve()
        self.assertNotEqual(_service_label(first), _service_label(second))
        self.assertNotEqual(_windows_task_name(first), _windows_task_name(second))
        self.assertTrue(_service_label(first).startswith(LABEL + "."))
        self.assertTrue(_windows_task_name(first).startswith(WINDOWS_TASK_NAME + " ("))


    @unittest.skipUnless(sys.platform == "darwin", "macOS launchd test")
    @patch("multiagentos.mcp_service._wait_for_endpoint", return_value=False)
    @patch("multiagentos.mcp_service._launchctl")
    @patch("multiagentos.mcp_service.shutil.which", return_value="/usr/local/bin/multiagentos")
    def test_install_endpoint_timeout_rolls_back_new_service(self, which, launchctl, endpoint):
        from subprocess import CompletedProcess

        def launchctl_side_effect(*args, **kwargs):
            if args[0] == "bootstrap":
                return CompletedProcess(args, 0, "", "")
            if args[0] == "kickstart":
                return CompletedProcess(args, 0, "", "")
            return CompletedProcess(args, 1, "", "")

        launchctl.side_effect = launchctl_side_effect
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("multiagentos.mcp_service.LAUNCH_AGENTS_DIR", root / "LaunchAgents"):
                with patch.object(sys, "platform", "darwin"):
                    with self.assertRaisesRegex(RuntimeError, "did not start within 30 seconds"):
                        install_mcp_service(root)
            self.assertFalse(list((root / "LaunchAgents").glob("*.plist")))

        bootouts = [call for call in launchctl.call_args_list if call.args[0] == "bootout"]
        self.assertGreaterEqual(len(bootouts), 2)

    @unittest.skipUnless(sys.platform == "darwin", "macOS launchd test")
    @patch("multiagentos.mcp_service._wait_for_endpoint", return_value=True)
    @patch("multiagentos.mcp_service._launchctl")
    @patch("multiagentos.mcp_service.shutil.which", return_value="/usr/local/bin/multiagentos")
    def test_install_waits_for_unload_before_bootstrap(self, which, launchctl, endpoint):
        from subprocess import CompletedProcess

        calls = []

        def launchctl_side_effect(*args, **kwargs):
            calls.append(args)
            if args[0] == "bootstrap":
                return CompletedProcess(args, 0, "", "")
            if args[0] == "kickstart":
                return CompletedProcess(args, 0, "", "")
            return CompletedProcess(args, 1, "", "")

        launchctl.side_effect = launchctl_side_effect
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("multiagentos.mcp_service.LAUNCH_AGENTS_DIR", root / "LaunchAgents"):
                with patch.object(sys, "platform", "darwin"):
                    install_mcp_service(root)

        bootstrap_index = next(i for i, args in enumerate(calls) if args[0] == "bootstrap")
        print_indices = [i for i, args in enumerate(calls[:bootstrap_index]) if args[0] == "print"]
        self.assertTrue(print_indices)
        self.assertLess(print_indices[-1], bootstrap_index)

    @unittest.skipUnless(sys.platform == "darwin", "macOS launchd test")
    @patch("multiagentos.mcp_service._launchctl")
    def test_uninstall_waits_for_service_to_unload_before_removing_plist(self, launchctl):
        from subprocess import CompletedProcess

        calls = []
        launchctl.side_effect = lambda *args, **kwargs: (
            calls.append(args) or CompletedProcess(args, 1, "", "")
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            launch_dir = root / "LaunchAgents"
            launch_dir.mkdir()
            plist = launch_dir / f"{_service_label(root)}.plist"
            plist.write_bytes(b"old")
            with patch("multiagentos.mcp_service.LAUNCH_AGENTS_DIR", launch_dir):
                with patch.object(sys, "platform", "darwin"):
                    uninstall_mcp_service(root)
            self.assertFalse(plist.exists())

        self.assertEqual(calls[0][0], "bootout")
        self.assertEqual(calls[1][0], "print")


if __name__ == "__main__":
    unittest.main()

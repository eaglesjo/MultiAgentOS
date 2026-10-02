import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from multiagentos import windows_launcher


class WindowsLauncherTests(unittest.TestCase):
    def test_main_forwards_mcp_serve_http_arguments(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            argv = [
                "pythonw",
                "--path",
                str(root),
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--allow-write",
            ]
            with patch.object(sys, "argv", argv):
                with patch.object(windows_launcher, "_log_path", return_value=root / "mcp.log"):
                    with patch("multiagentos.cli.main", return_value=0) as cli_main:
                        result = windows_launcher.main()

            self.assertEqual(result, 0)
            cli_main.assert_called_once_with()
            self.assertEqual(
                sys.argv,
                [
                    "pythonw",
                    "mcp",
                    "serve-http",
                    "--path",
                    str(root),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                    "--allow-write",
                ],
            )


if __name__ == "__main__":
    unittest.main()

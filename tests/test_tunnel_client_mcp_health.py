from __future__ import annotations

import unittest

from tests.tunnel_client_mcp_health import validate


class TunnelClientMCPHealthTest(unittest.TestCase):
    def _payload(self) -> dict[str, object]:
        return {
            "status": "ok",
            "state": "discovered",
            "limited": False,
            "details": {
                "limited": False,
                "tools_list": {
                    "ok": True,
                    "complete": True,
                    "partial": False,
                    "limited": False,
                    "tool_names": ["filesystem.read"],
                },
            },
        }

    def test_accepts_complete_discovery(self) -> None:
        self.assertEqual(validate(self._payload()), [])

    def test_rejects_incomplete_tools_list(self) -> None:
        payload = self._payload()
        tools_list = payload["details"]["tools_list"]
        tools_list["complete"] = False
        errors = validate(payload)
        self.assertIn("MCP tools_list evidence is not complete", errors)

    def test_rejects_missing_expected_tool(self) -> None:
        payload = self._payload()
        tools_list = payload["details"]["tools_list"]
        tools_list["tool_names"] = ["git.status"]
        errors = validate(payload)
        self.assertIn("expected MCP tool is missing: filesystem.read", errors)

    def test_rejects_limited_discovery(self) -> None:
        payload = self._payload()
        payload["details"]["limited"] = True
        errors = validate(payload)
        self.assertIn("MCP discovery evidence is limited", errors)

    def test_requires_filesystem_write_when_requested(self) -> None:
        import os

        payload = self._payload()
        os.environ["EXPECT_FILESYSTEM_WRITE"] = "1"
        try:
            errors = validate(payload)
        finally:
            os.environ.pop("EXPECT_FILESYSTEM_WRITE", None)
        self.assertIn("expected MCP tool is missing: filesystem.write", errors)

    def test_accepts_filesystem_write_when_requested(self) -> None:
        import os

        payload = self._payload()
        payload["details"]["tools_list"]["tool_names"].append("filesystem.write")
        os.environ["EXPECT_FILESYSTEM_WRITE"] = "1"
        try:
            errors = validate(payload)
        finally:
            os.environ.pop("EXPECT_FILESYSTEM_WRITE", None)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()

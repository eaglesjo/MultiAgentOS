from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

from tests.tunnel_client_runtime_status import main


class TunnelClientRuntimeStatusTest(unittest.TestCase):
    def _run(self, payload: dict[str, object]) -> tuple[int, str, str]:
        import sys

        old_stdin = sys.stdin
        sys.stdin = io.StringIO(json.dumps(payload))
        out = io.StringIO()
        err = io.StringIO()
        try:
            with redirect_stdout(out), redirect_stderr(err):
                code = main()
        finally:
            sys.stdin = old_stdin
        return code, out.getvalue(), err.getvalue()

    def test_accepts_healthy_runtime(self) -> None:
        code, out, err = self._run(
            {
                "process_running": True,
                "healthy": True,
                "ready": True,
                "control_plane_poll_health": {"status": "ok"},
            }
        )
        self.assertEqual(code, 0)
        self.assertIn("control_plane_poll_health=ok", out)
        self.assertEqual(err, "")

    def test_rejects_unhealthy_control_plane(self) -> None:
        code, out, err = self._run(
            {
                "process_running": True,
                "healthy": True,
                "ready": True,
                "control_plane_poll_health": {"status": "degraded"},
            }
        )
        self.assertEqual(code, 1)
        self.assertIn("control_plane_poll_health is not healthy", err)

    def test_rejects_missing_readiness_fields(self) -> None:
        code, out, err = self._run(
            {
                "process_running": True,
                "healthy": True,
                "control_plane_poll_health": "ok",
            }
        )
        self.assertEqual(code, 1)
        self.assertIn("ready must be true", err)


if __name__ == "__main__":
    unittest.main()

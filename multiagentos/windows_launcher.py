"""Windowless Windows launcher for the managed local MCP service."""

from __future__ import annotations

import sys
from pathlib import Path


def _log_path() -> Path:
    # Task Scheduler sets the working directory to the project root.
    root = Path.cwd()
    logs = root / ".multiagentos" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return logs / "mcp-windows.log"


def main() -> int:
    log_path = _log_path()
    with log_path.open("a", encoding="utf-8", buffering=1) as log:
        sys.stdout = log
        sys.stderr = log
        try:
            # pythonw.exe invokes this module directly, so forward the
            # original server options into the normal CLI command.
            sys.argv[1:1] = ["mcp", "serve-http"]
            from multiagentos.cli import main as cli_main

            return int(cli_main())
        except BaseException:
            import traceback

            traceback.print_exc()
            raise


if __name__ == "__main__":
    raise SystemExit(main())

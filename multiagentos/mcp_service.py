"""macOS launchd lifecycle helpers for the local MultiAgentOS MCP server."""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

LABEL = "com.eaglesjo.multiagentos.mcp"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_PATH = LAUNCH_AGENTS_DIR / f"{LABEL}.plist"


def _require_macos() -> None:
    if sys.platform != "darwin":
        raise RuntimeError("The local MCP launchd service is supported on macOS only.")


def _launchctl(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["launchctl", *args],
        check=check,
        text=True,
        capture_output=True,
    )


def _target() -> str:
    return f"gui/{os.getuid()}/{LABEL}"


def install_mcp_service(
    project_root: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    allow_write: bool = False,
    allow_process: bool = False,
) -> str:
    """Install and start the local MCP server as a per-user launchd service."""
    _require_macos()
    project_root = project_root.expanduser().resolve()

    if not project_root.is_dir():
        raise ValueError(f"Project path does not exist: {project_root}")
    if host != "127.0.0.1":
        raise ValueError("The managed local MCP service only supports host 127.0.0.1.")
    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535.")

    executable = shutil.which("multiagentos")
    if executable:
        program_arguments = [
            executable,
            "mcp",
            "serve-http",
            "--path",
            str(project_root),
            "--host",
            host,
            "--port",
            str(port),
        ]
    else:
        program_arguments = [
            sys.executable,
            "-m",
            "multiagentos.cli",
            "mcp",
            "serve-http",
            "--path",
            str(project_root),
            "--host",
            host,
            "--port",
            str(port),
        ]

    if allow_write:
        program_arguments.append("--allow-write")
    if allow_process:
        program_arguments.append("--allow-process")

    logs = project_root / ".multiagentos" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    plist = {
        "Label": LABEL,
        "ProgramArguments": program_arguments,
        "WorkingDirectory": str(project_root),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 5,
        "ProcessType": "Background",
        "StandardOutPath": str(logs / "mcp-launchd.log"),
        "StandardErrorPath": str(logs / "mcp-launchd.error.log"),
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
    }
    PLIST_PATH.write_bytes(plistlib.dumps(plist))

    _launchctl("bootout", _target(), check=False)
    # A plist in ~/Library/LaunchAgents is user-owned. Use launchctl's
    # domain target for a stable per-user service across login/reboot.
    domain = f"gui/{os.getuid()}"
    bootstrap = _launchctl("bootstrap", domain, str(PLIST_PATH), check=False)
    if bootstrap.returncode != 0:
        # launchctl may report an existing service even after bootout returned
        # successfully. Treat "already bootstrapped" as recoverable by loading
        # the plist through the domain target once more.
        if "service already loaded" not in bootstrap.stderr.lower():
            raise subprocess.CalledProcessError(
                bootstrap.returncode,
                bootstrap.args,
                output=bootstrap.stdout,
                stderr=bootstrap.stderr,
            )
    _launchctl("kickstart", "-k", _target())
    _launchctl("print", _target())

    return (
        "MultiAgentOS local MCP service installed and started. "
        f"Endpoint: http://{host}:{port}/mcp. "
        "launchd will restart it after login/reboot."
    )


def uninstall_mcp_service() -> str:
    """Stop and remove the managed local MCP launchd service."""
    _require_macos()
    _launchctl("bootout", _target(), check=False)
    PLIST_PATH.unlink(missing_ok=True)
    return f"MultiAgentOS local MCP service removed: {LABEL}"


def mcp_service_status() -> str:
    """Return the launchd status for the managed local MCP service."""
    _require_macos()
    result = _launchctl("print", _target(), check=False)
    if result.returncode == 0:
        return result.stdout.strip()
    return f"MultiAgentOS local MCP service is not installed: {LABEL}"


__all__ = [
    "LABEL",
    "PLIST_PATH",
    "install_mcp_service",
    "uninstall_mcp_service",
    "mcp_service_status",
]

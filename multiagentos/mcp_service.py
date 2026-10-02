"""Local MCP service lifecycle helpers for macOS and Windows."""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

LABEL = "com.eaglesjo.multiagentos.mcp"
WINDOWS_TASK_NAME = "MultiAgentOS Local MCP"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_PATH = LAUNCH_AGENTS_DIR / f"{LABEL}.plist"


def _require_supported_platform() -> None:
    if sys.platform not in {"darwin", "win32"}:
        raise RuntimeError("The local MCP managed service is supported on macOS and Windows only.")


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


def _schtasks(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["schtasks.exe", *args],
        check=check,
        text=True,
        capture_output=True,
    )


def _target() -> str:
    return f"gui/{os.getuid()}/{LABEL}"


def _validate_install_args(project_root: Path, host: str, port: int) -> Path:
    project_root = project_root.expanduser().resolve()
    if not project_root.is_dir():
        raise ValueError(f"Project path does not exist: {project_root}")
    if host != "127.0.0.1":
        raise ValueError("The managed local MCP service only supports host 127.0.0.1.")
    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535.")
    return project_root


def _program_arguments(
    project_root: Path,
    *,
    host: str,
    port: int,
    allow_write: bool,
    allow_process: bool,
) -> list[str]:
    if sys.platform == "win32":
        program_arguments = [sys.executable, "-m", "multiagentos.cli", "mcp", "serve-http"]
    else:
        executable = shutil.which("multiagentos")
        program_arguments = (
            [executable, "mcp", "serve-http"]
            if executable
            else [sys.executable, "-m", "multiagentos.cli", "mcp", "serve-http"]
        )
    program_arguments.extend(
        ["--path", str(project_root), "--host", host, "--port", str(port)]
    )
    if allow_write:
        program_arguments.append("--allow-write")
    if allow_process:
        program_arguments.append("--allow-process")
    return program_arguments


def _windows_quote_argument(value: str) -> str:
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'


def _windows_task_command(program_arguments: list[str]) -> str:
    return " ".join(
        _windows_quote_argument(arg) if " " in arg else arg
        for arg in program_arguments
    )


def install_mcp_service(
    project_root: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    allow_write: bool = False,
    allow_process: bool = False,
) -> str:
    """Install and start the local MCP server as a per-user OS service."""
    _require_supported_platform()
    project_root = _validate_install_args(project_root, host, port)
    program_arguments = _program_arguments(
        project_root,
        host=host,
        port=port,
        allow_write=allow_write,
        allow_process=allow_process,
    )

    if sys.platform == "darwin":
        return _install_macos(
            project_root,
            program_arguments,
            host=host,
            port=port,
        )

    return _install_windows(
        project_root,
        program_arguments,
        host=host,
        port=port,
    )


def _install_macos(
    project_root: Path,
    program_arguments: list[str],
    *,
    host: str,
    port: int,
) -> str:
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
    domain = f"gui/{os.getuid()}"
    bootstrap = _launchctl("bootstrap", domain, str(PLIST_PATH), check=False)
    if bootstrap.returncode != 0:
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


def _install_windows(
    project_root: Path,
    program_arguments: list[str],
    *,
    host: str,
    port: int,
) -> str:
    task_command = _windows_task_command(program_arguments)
    result = _schtasks(
        "/Create",
        "/TN",
        WINDOWS_TASK_NAME,
        "/TR",
        task_command,
        "/SC",
        "ONLOGON",
        "/RL",
        "LIMITED",
        "/F",
        check=False,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )

    run = _schtasks("/Run", "/TN", WINDOWS_TASK_NAME, check=False)
    if run.returncode != 0:
        raise subprocess.CalledProcessError(
            run.returncode,
            run.args,
            output=run.stdout,
            stderr=run.stderr,
        )

    return (
        "MultiAgentOS local MCP service installed and started. "
        f"Endpoint: http://{host}:{port}/mcp. "
        "Task Scheduler will start it at user logon."
    )


def uninstall_mcp_service() -> str:
    """Stop and remove the managed local MCP service."""
    _require_supported_platform()
    if sys.platform == "darwin":
        _launchctl("bootout", _target(), check=False)
        PLIST_PATH.unlink(missing_ok=True)
        return f"MultiAgentOS local MCP service removed: {LABEL}"

    _schtasks("/End", "/TN", WINDOWS_TASK_NAME, check=False)
    result = _schtasks("/Delete", "/TN", WINDOWS_TASK_NAME, "/F", check=False)
    if result.returncode not in {0, 1}:
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
    return f"MultiAgentOS local MCP service removed: {WINDOWS_TASK_NAME}"


def mcp_service_status() -> str:
    """Return the status for the managed local MCP service."""
    _require_supported_platform()
    if sys.platform == "darwin":
        result = _launchctl("print", _target(), check=False)
        if result.returncode == 0:
            return result.stdout.strip()
        return f"MultiAgentOS local MCP service is not installed: {LABEL}"

    result = _schtasks("/Query", "/TN", WINDOWS_TASK_NAME, "/FO", "LIST", "/V", check=False)
    if result.returncode == 0:
        return result.stdout.strip()
    return f"MultiAgentOS local MCP service is not installed: {WINDOWS_TASK_NAME}"


__all__ = [
    "LABEL",
    "WINDOWS_TASK_NAME",
    "PLIST_PATH",
    "install_mcp_service",
    "uninstall_mcp_service",
    "mcp_service_status",
]

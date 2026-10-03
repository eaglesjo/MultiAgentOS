"""Local MCP service lifecycle helpers for macOS and Windows."""

from __future__ import annotations

import getpass
import hashlib
import os
import plistlib
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

LABEL = "com.eaglesjo.multiagentos.mcp"
WINDOWS_TASK_NAME = "MultiAgentOS Local MCP"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_PATH = LAUNCH_AGENTS_DIR / f"{LABEL}.plist"


def _service_id(project_root: Path) -> str:
    return hashlib.sha256(str(project_root).encode("utf-8")).hexdigest()[:12]


def _service_label(project_root: Path) -> str:
    return f"{LABEL}.{_service_id(project_root)}"


def _windows_task_name(project_root: Path) -> str:
    return f"{WINDOWS_TASK_NAME} ({_service_id(project_root)})"


def _plist_path(project_root: Path) -> Path:
    return LAUNCH_AGENTS_DIR / f"{_service_label(project_root)}.plist"
WINDOWS_TASK_NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"


def _require_supported_platform() -> None:
    if sys.platform not in {"darwin", "win32"}:
        raise RuntimeError("The local MCP managed service is supported on macOS and Windows only.")


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


def _target(project_root: Path) -> str:
    return f"gui/{os.getuid()}/{_service_label(project_root)}"


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
        # pythonw.exe has no stdout/stderr streams. Use a small module launcher
        # that redirects both streams to the project log before importing Uvicorn.
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        interpreter = str(pythonw) if pythonw.is_file() else sys.executable
        program_arguments = [interpreter, "-m", "multiagentos.windows_launcher"]
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
        _windows_quote_argument(arg) if i == 0 or " " in arg else arg
        for i, arg in enumerate(program_arguments)
    )


def _windows_task_user() -> str:
    domain = os.environ.get("USERDOMAIN")
    username = os.environ.get("USERNAME") or getpass.getuser()
    return f"{domain}\\{username}" if domain else username


def _windows_task_xml(
    program_arguments: list[str],
    *,
    project_root: Path,
) -> str:
    command = program_arguments[0]
    arguments = _windows_task_command(program_arguments[1:])
    user = _windows_task_user()
    ns = WINDOWS_TASK_NS
    ET.register_namespace("", ns)

    task = ET.Element(f"{{{ns}}}Task", {"version": "1.2"})
    registration = ET.SubElement(task, f"{{{ns}}}RegistrationInfo")
    ET.SubElement(registration, f"{{{ns}}}Author").text = user
    ET.SubElement(registration, f"{{{ns}}}Description").text = (
        "MultiAgentOS local MCP service"
    )

    principals = ET.SubElement(task, f"{{{ns}}}Principals")
    principal = ET.SubElement(principals, f"{{{ns}}}Principal", {"id": "Author"})
    ET.SubElement(principal, f"{{{ns}}}UserId").text = user
    ET.SubElement(principal, f"{{{ns}}}LogonType").text = "InteractiveToken"
    ET.SubElement(principal, f"{{{ns}}}RunLevel").text = "LeastPrivilege"

    settings = ET.SubElement(task, f"{{{ns}}}Settings")
    ET.SubElement(settings, f"{{{ns}}}Enabled").text = "true"
    ET.SubElement(settings, f"{{{ns}}}AllowStartOnDemand").text = "true"
    ET.SubElement(settings, f"{{{ns}}}AllowHardTerminate").text = "true"
    ET.SubElement(settings, f"{{{ns}}}StartWhenAvailable").text = "true"
    ET.SubElement(settings, f"{{{ns}}}DisallowStartIfOnBatteries").text = "false"
    ET.SubElement(settings, f"{{{ns}}}StopIfGoingOnBatteries").text = "false"
    ET.SubElement(settings, f"{{{ns}}}RunOnlyIfIdle").text = "false"
    ET.SubElement(settings, f"{{{ns}}}ExecutionTimeLimit").text = "PT0S"

    triggers = ET.SubElement(task, f"{{{ns}}}Triggers")
    logon = ET.SubElement(triggers, f"{{{ns}}}LogonTrigger")
    ET.SubElement(logon, f"{{{ns}}}Enabled").text = "true"
    ET.SubElement(logon, f"{{{ns}}}UserId").text = user

    actions = ET.SubElement(task, f"{{{ns}}}Actions", {"Context": "Author"})
    action = ET.SubElement(actions, f"{{{ns}}}Exec")
    ET.SubElement(action, f"{{{ns}}}Command").text = command
    if arguments:
        ET.SubElement(action, f"{{{ns}}}Arguments").text = arguments
    ET.SubElement(action, f"{{{ns}}}WorkingDirectory").text = str(project_root)

    xml = ET.tostring(task, encoding="unicode", xml_declaration=True)
    return xml.replace("encoding='utf-8'", "encoding='UTF-16'")


def _wait_for_endpoint(host: str, port: int, *, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def _wait_for_service_unloaded(target: str, *, timeout: float = 5.0) -> None:
    """Wait until launchd no longer reports a service target."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = _launchctl("print", target, check=False)
        if result.returncode != 0:
            return
        time.sleep(0.1)
    raise RuntimeError(f"launchd service did not unload within {timeout:.1f}s: {target}")


def _write_plist_atomically(plist_path: Path, plist: dict) -> None:
    """Write a launchd plist atomically so launchd never sees a partial file."""
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{plist_path.name}.", suffix=".tmp", dir=plist_path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(plistlib.dumps(plist))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, plist_path)
    finally:
        Path(temp_name).unlink(missing_ok=True)


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
        "Label": _service_label(project_root),
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
    plist_path = _plist_path(project_root)
    target = _target(project_root)
    domain = f"gui/{os.getuid()}"

    previous_plist = plist_path.read_bytes() if plist_path.exists() else None
    _launchctl("bootout", target, check=False)
    _wait_for_service_unloaded(target)

    try:
        _write_plist_atomically(plist_path, plist)

        bootstrap = _launchctl("bootstrap", domain, str(plist_path), check=False)
        if bootstrap.returncode != 0:
            raise subprocess.CalledProcessError(
                bootstrap.returncode,
                bootstrap.args,
                output=bootstrap.stdout,
                stderr=bootstrap.stderr,
            )

        kickstart = _launchctl("kickstart", "-k", target, check=False)
        if kickstart.returncode != 0:
            raise subprocess.CalledProcessError(
                kickstart.returncode,
                kickstart.args,
                output=kickstart.stdout,
                stderr=kickstart.stderr,
            )

        if not _wait_for_endpoint(host, port):
            raise RuntimeError(
                "launchd registered the MultiAgentOS local MCP service, "
                f"but http://{host}:{port}/mcp did not start within 30 seconds."
            )

        _launchctl("print", target)
    except Exception:
        # Never leave a half-installed project service behind. Restore the
        # previous project plist when one existed, without touching other
        # project-scoped launchd services.
        _launchctl("bootout", target, check=False)
        try:
            _wait_for_service_unloaded(target)
        except Exception:
            pass

        if previous_plist is None:
            plist_path.unlink(missing_ok=True)
        else:
            try:
                plist_path.write_bytes(previous_plist)
                restored = _launchctl("bootstrap", domain, str(plist_path), check=False)
                if restored.returncode == 0:
                    _launchctl("kickstart", "-k", target, check=False)
            except Exception:
                # Preserve the original install failure; the failed install
                # must not mask it with a best-effort rollback error.
                pass
        raise

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
    logs = project_root / ".multiagentos" / "logs"
    logs.mkdir(parents=True, exist_ok=True)

    _schtasks("/End", "/TN", WINDOWS_TASK_NAME, check=False)
    _schtasks("/Delete", "/TN", WINDOWS_TASK_NAME, "/F", check=False)

    xml = _windows_task_xml(program_arguments, project_root=project_root)
    xml_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-16",
            suffix=".xml",
            prefix="multiagentos-task-",
            dir=logs,
            delete=False,
        ) as handle:
            handle.write(xml)
            xml_path = handle.name

        result = _schtasks(
            "/Create",
            "/XML",
            xml_path,
            "/TN",
            _windows_task_name(project_root),
            "/F",
            check=False,
        )
    finally:
        if xml_path:
            Path(xml_path).unlink(missing_ok=True)

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "no diagnostic output").strip()
        raise RuntimeError(
            "Windows Task Scheduler could not register the MultiAgentOS local MCP task "
            f"(exit code {result.returncode}): {detail}"
        )

    run = _schtasks("/Run", "/TN", _windows_task_name(project_root), check=False)
    if run.returncode != 0:
        raise subprocess.CalledProcessError(
            run.returncode,
            run.args,
            output=run.stdout,
            stderr=run.stderr,
        )

    if not _wait_for_endpoint(host, port):
        raise RuntimeError(
            "Windows Task Scheduler registered the MultiAgentOS local MCP task, "
            f"but http://{host}:{port}/mcp did not start within 30 seconds."
        )

    return (
        "MultiAgentOS local MCP service installed and started. "
        f"Endpoint: http://{host}:{port}/mcp. "
        "Task Scheduler will start it at user logon."
    )


def uninstall_mcp_service(project_root: Path = Path(".")) -> str:
    """Stop and remove the managed local MCP service for a project."""
    _require_supported_platform()
    project_root = _validate_install_args(project_root, "127.0.0.1", 8000)
    if sys.platform == "darwin":
        label = _service_label(project_root)
        target = _target(project_root)
        _launchctl("bootout", target, check=False)
        _wait_for_service_unloaded(target)
        _plist_path(project_root).unlink(missing_ok=True)
        return f"MultiAgentOS local MCP service removed: {label}"

    task_name = _windows_task_name(project_root)
    _schtasks("/End", "/TN", task_name, check=False)
    _schtasks("/End", "/TN", WINDOWS_TASK_NAME, check=False)
    result = _schtasks("/Delete", "/TN", task_name, "/F", check=False)
    _schtasks("/Delete", "/TN", WINDOWS_TASK_NAME, "/F", check=False)
    if result.returncode not in {0, 1}:
        raise subprocess.CalledProcessError(result.returncode, result.args, output=result.stdout, stderr=result.stderr)
    return f"MultiAgentOS local MCP service removed: {task_name}"


def mcp_service_status(project_root: Path = Path(".")) -> str:
    """Return the status for the managed local MCP service for a project."""
    _require_supported_platform()
    project_root = _validate_install_args(project_root, "127.0.0.1", 8000)
    if sys.platform == "darwin":
        label = _service_label(project_root)
        result = _launchctl("print", _target(project_root), check=False)
        if result.returncode == 0:
            return result.stdout.strip()
        return f"MultiAgentOS local MCP service is not installed: {label}"

    task_name = _windows_task_name(project_root)
    result = _schtasks("/Query", "/TN", task_name, "/FO", "LIST", "/V", check=False)
    if result.returncode == 0:
        return result.stdout.strip()
    return f"MultiAgentOS local MCP service is not installed: {task_name}"

__all__ = [
    "LABEL",
    "WINDOWS_TASK_NAME",
    "PLIST_PATH",
    "install_mcp_service",
    "uninstall_mcp_service",
    "mcp_service_status",
]

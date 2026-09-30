"""Process-boundary E2E test for durable MCP recovery.

The first MCP server process is intentionally terminated after the durable
STARTED ledger record is persisted. A fresh MCP server process then recovers
the same invocation through the stdio JSON-RPC boundary.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from runtime import AgentExecutionRuntime


def _send(proc: subprocess.Popen[str], message: dict[str, object]) -> dict[str, object]:
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("MCP server closed stdout unexpectedly")
    response = json.loads(line)
    if not isinstance(response, dict):
        raise RuntimeError("MCP response is not a JSON object")
    return response


def _notify(proc: subprocess.Popen[str], message: dict[str, object]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
    proc.stdin.flush()


def _initialize(proc: subprocess.Popen[str]) -> None:
    response = _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "agent-execution-runtime-mcp-e2e", "version": "1.0"},
            },
        },
    )
    assert response["result"]["serverInfo"]["name"] == "Agent Execution Runtime"
    _notify(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})


def _server(root: Path, *, crash_after_started: bool, allow_write: bool = False) -> subprocess.Popen[str]:
    if not crash_after_started:
        command = [
            sys.executable,
            "-m",
            "multiagentos.cli",
            "mcp",
            "serve",
            "--path",
            str(root),
        ]
        if allow_write:
            command.append("--allow-write")
    else:
        launcher = textwrap.dedent(
            """
            import os
            import sys
            from pathlib import Path
            from runtime.mcp.server import AgentExecutionRuntimeMCPServer

            root = Path(sys.argv[1])
            server = AgentExecutionRuntimeMCPServer(root, allow_write=bool(int(sys.argv[2])))

            def crash_before_tool_execution(*args, **kwargs):
                os._exit(97)

            server.durable_bridge.tool_runtime.execute = crash_before_tool_execution
            server.serve_forever()
            """
        )
        command = [sys.executable, "-c", launcher, str(root), "1" if allow_write else "0"]

    return subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_mcp_stdio_crash_restart_recovers_same_safe_invocation() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        target = root / "mcp-recovery.txt"
        target.write_text("durable MCP recovery", encoding="utf-8")

        crashed = _server(root, crash_after_started=True)
        try:
            _initialize(crashed)
            try:
                _send(
                    crashed,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "filesystem.read",
                            "arguments": {"path": target.name},
                        },
                    },
                )
            except RuntimeError:
                pass
            else:
                raise AssertionError("crash-boundary MCP process unexpectedly returned a response")
        finally:
            if crashed.poll() is None:
                crashed.kill()
            crashed.wait(timeout=5)

        runtime = AgentExecutionRuntime()
        work_ids = runtime.state_store(root).list_ids()
        assert len(work_ids) == 1
        work_unit_id = work_ids[0]

        snapshot = runtime.inspect_work_unit(root, work_unit_id)
        assert snapshot["execution_state"] == "tool_in_flight"
        assert snapshot["pending_tool_call_ids"]

        unresolved = runtime.tool_ledger_store(root).unresolved(work_unit_id)
        assert len(unresolved) == 1
        original = unresolved[0]
        assert original.tool_id == "filesystem.read"
        assert original.idempotency_key == original.invocation_id

        recovered = _server(root, crash_after_started=False)
        try:
            _initialize(recovered)
            response = _send(
                recovered,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "runtime/recover",
                    "params": {"workUnitId": work_unit_id},
                },
            )
            assert response["result"]["disposition"] == "completed"
            assert response["result"]["replayed"] is True
            assert response["result"]["invocation_id"] == original.invocation_id
            assert response["result"]["idempotency_key"] == original.idempotency_key

            read = _send(
                recovered,
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "filesystem.read",
                        "arguments": {"path": target.name},
                    },
                },
            )
            assert read["result"]["isError"] is False
            assert read["result"]["content"][0]["text"] == "durable MCP recovery"
        finally:
            recovered.terminate()
            recovered.wait(timeout=5)

        final = runtime.inspect_work_unit(root, work_unit_id)
        assert final["execution_state"] == "completed"
        assert final["work_status"] == "completed"

        ledger = runtime.tool_ledger_store(root).load(work_unit_id)
        assert ledger[-1].state.value == "completed"
        assert ledger[-1].invocation_id == original.invocation_id
        assert ledger[-1].idempotency_key == original.idempotency_key


def test_mcp_stdio_recovery_is_idempotent_and_side_effects_require_review() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        target = root / "mcp-recovery.txt"
        target.write_text("durable MCP recovery", encoding="utf-8")

        crashed = _server(root, crash_after_started=True)
        try:
            _initialize(crashed)
            try:
                _send(
                    crashed,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "filesystem.read",
                            "arguments": {"path": target.name},
                        },
                    },
                )
            except RuntimeError:
                pass
        finally:
            if crashed.poll() is None:
                crashed.kill()
            crashed.wait(timeout=5)

        runtime = AgentExecutionRuntime()
        work_unit_id = runtime.state_store(root).list_ids()[0]
        original = runtime.tool_ledger_store(root).unresolved(work_unit_id)[0]

        recovered = _server(root, crash_after_started=False)
        try:
            _initialize(recovered)
            first = _send(
                recovered,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "runtime/recover",
                    "params": {"workUnitId": work_unit_id},
                },
            )
            second = _send(
                recovered,
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "runtime/recover",
                    "params": {"workUnitId": work_unit_id},
                },
            )
            assert first["result"]["replayed"] is True
            assert first["result"]["invocation_id"] == original.invocation_id
            assert second["result"]["replayed"] is False
            assert second["result"]["disposition"] == "completed"
        finally:
            recovered.terminate()
            recovered.wait(timeout=5)

        assert runtime.recovery_plan(root, work_unit_id).disposition.value == "completed"



def test_mcp_stdio_side_effecting_crash_requires_human_review() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        target = root / "side-effect.txt"
        target.write_text("before", encoding="utf-8")

        crashed = _server(root, crash_after_started=True, allow_write=True)
        try:
            _initialize(crashed)
            try:
                _send(
                    crashed,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "filesystem.write",
                            "arguments": {"path": target.name, "content": "after"},
                        },
                    },
                )
            except RuntimeError:
                pass
        finally:
            if crashed.poll() is None:
                crashed.kill()
            crashed.wait(timeout=5)

        runtime = AgentExecutionRuntime()
        work_unit_id = runtime.state_store(root).list_ids()[0]
        assert target.read_text(encoding="utf-8") == "before"
        assert runtime.recovery_plan(root, work_unit_id).disposition.value == "review_required"

        recovered = _server(root, crash_after_started=False, allow_write=True)
        try:
            _initialize(recovered)
            response = _send(
                recovered,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "runtime/recover",
                    "params": {"workUnitId": work_unit_id},
                },
            )
            assert response["result"]["replayed"] is False
            assert response["result"]["disposition"] == "review_required"
        finally:
            recovered.terminate()
            recovered.wait(timeout=5)

        assert target.read_text(encoding="utf-8") == "before"
        decisions = runtime.decision_store(root).load(work_unit_id)
        assert any(
            decision.category.value == "recovery"
            and decision.disposition.value == "review_required"
            for decision in decisions
        )


def test_mcp_stdio_side_effecting_recovery_human_approve_replays_once() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        target = root / "approved-side-effect.txt"
        target.write_text("before", encoding="utf-8")
        crashed = _server(root, crash_after_started=True, allow_write=True)
        try:
            _initialize(crashed)
            try:
                _send(crashed, {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "filesystem.write", "arguments": {"path": target.name, "content": "after"}}})
            except RuntimeError:
                pass
        finally:
            if crashed.poll() is None:
                crashed.kill()
            crashed.wait(timeout=5)
        runtime = AgentExecutionRuntime()
        work_unit_id = runtime.state_store(root).list_ids()[0]
        recovered = _server(root, crash_after_started=False, allow_write=True)
        try:
            _initialize(recovered)
            approved = _send(recovered, {"jsonrpc": "2.0", "id": 11, "method": "runtime/recover", "params": {"workUnitId": work_unit_id, "humanDecision": "approve", "notes": "Verified the interrupted write had not reached the filesystem."}})
            assert approved["result"]["disposition"] == "completed"
            assert approved["result"]["replayed"] is True
            assert approved["result"]["human_decision"] == "approve"
            assert target.read_text(encoding="utf-8") == "after"
            repeated = _send(recovered, {"jsonrpc": "2.0", "id": 12, "method": "runtime/recover", "params": {"workUnitId": work_unit_id, "humanDecision": "approve"}})
            assert repeated["result"]["disposition"] == "completed"
            assert repeated["result"]["replayed"] is False
        finally:
            recovered.terminate()
            recovered.wait(timeout=5)
        decisions = runtime.decision_store(root).load(work_unit_id)
        recovery_allows = [
            item
            for item in decisions
            if item["category"] == "recovery" and item["disposition"] == "allow"
        ]
        assert len(recovery_allows) == 1
        assert recovery_allows[0]["metadata"].get("human_decision") == "approve"


def test_mcp_stdio_side_effecting_recovery_human_reject_is_terminal_and_safe() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        target = root / "rejected-side-effect.txt"
        target.write_text("before", encoding="utf-8")
        crashed = _server(root, crash_after_started=True, allow_write=True)
        try:
            _initialize(crashed)
            try:
                _send(crashed, {"jsonrpc": "2.0", "id": 20, "method": "tools/call", "params": {"name": "filesystem.write", "arguments": {"path": target.name, "content": "after"}}})
            except RuntimeError:
                pass
        finally:
            if crashed.poll() is None:
                crashed.kill()
            crashed.wait(timeout=5)
        runtime = AgentExecutionRuntime()
        work_unit_id = runtime.state_store(root).list_ids()[0]
        recovered = _server(root, crash_after_started=False, allow_write=True)
        try:
            _initialize(recovered)
            rejected = _send(recovered, {"jsonrpc": "2.0", "id": 21, "method": "runtime/recover", "params": {"workUnitId": work_unit_id, "humanDecision": "reject", "notes": "Do not replay an uncertain side effect."}})
            assert rejected["result"]["disposition"] == "failed"
            assert rejected["result"]["replayed"] is False
            assert target.read_text(encoding="utf-8") == "before"
        finally:
            recovered.terminate()
            recovered.wait(timeout=5)
        assert runtime.state_store(root).load(work_unit_id).status.value == "failed"
        decisions = runtime.decision_store(root).load(work_unit_id)
        assert any(item["category"] == "recovery" and item["disposition"] == "deny" and item["metadata"].get("human_decision") == "reject" for item in decisions)

if __name__ == "__main__":
    test_mcp_stdio_crash_restart_recovers_same_safe_invocation()
    print("AGENT_EXECUTION_RUNTIME MCP stdio durable recovery E2E: PASS")

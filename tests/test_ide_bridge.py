import json
from urllib.request import Request, urlopen
import unittest

from core.contracts.ide import IDECommandResult, IDEEventKind, IDEKind
from runtime.ide.registry import IDEAdapterRegistry
from runtime.ide.runtime import IDERuntime
from runtime.ide.bridge import IDEBridge, IDEBridgeAuthorizationError, IDEBridgePolicy, IDEBridgeServer


class IDEBridgeTests(unittest.TestCase):
    def test_policy_requires_token(self):
        policy = IDEBridgePolicy(token="secret")
        with self.assertRaises(IDEBridgeAuthorizationError):
            policy.authorize(None)

    def test_authenticated_loopback_event(self):
        received = []
        bridge = IDEBridge(policy=IDEBridgePolicy(token="secret"), event_handler=received.append)
        server = IDEBridgeServer(bridge, host="127.0.0.1", port=0)
        server.start()
        try:
            body = json.dumps({
                "kind": "context_changed",
                "context": {"kind": "vs_code", "project_root": "/tmp/project"},
                "payload": {},
            }).encode()
            request = Request(
                f"http://127.0.0.1:{server.server.server_port}/v1/ide/event",
                data=body,
                headers={"Authorization": "Bearer secret", "Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                self.assertEqual(response.status, 200)
            self.assertEqual(received[0].kind, IDEEventKind.CONTEXT_CHANGED)
            self.assertEqual(received[0].context.kind, IDEKind.VS_CODE)
        finally:
            server.stop()

    def test_authenticated_work_endpoint_uses_work_handler(self):
        received = []
        bridge = IDEBridge(policy=IDEBridgePolicy(token="secret"), work_handler=received.append)
        server = IDEBridgeServer(bridge, host="127.0.0.1", port=0)
        server.start()
        try:
            body = json.dumps({
                "objective": "Explain this file",
                "agent_id": "coder",
                "model_ids": ["fake-model"],
                "context": {"kind": "vs_code", "project_root": "/tmp/project", "file_path": "/tmp/project/main.py"},
            }).encode()
            request = Request(
                f"http://127.0.0.1:{server.server.server_port}/v1/ide/work",
                data=body,
                headers={"Authorization": "Bearer secret", "Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                payload = json.loads(response.read())
            self.assertTrue(payload["ok"])
            self.assertEqual(received[0].objective, "Explain this file")
            self.assertEqual(received[0].agent_id, "coder")
            self.assertEqual(received[0].context.kind, IDEKind.VS_CODE)
        finally:
            server.stop()

    def test_wrong_token_is_rejected(self):
        bridge = IDEBridge(policy=IDEBridgePolicy(token="secret"))
        server = IDEBridgeServer(bridge, host="127.0.0.1", port=0)
        server.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.server.server_port}/v1/ide/event",
                data=b'{"kind":"context_changed","context":{"kind":"vs_code","project_root":"/tmp"}}',
                headers={"Authorization": "Bearer wrong"},
                method="POST",
            )
            with self.assertRaises(Exception) as exc:
                urlopen(request)
            self.assertIn("401", str(exc.exception))
        finally:
            server.stop()

    def test_remote_bind_requires_explicit_policy(self):
        bridge = IDEBridge(policy=IDEBridgePolicy(token="secret"))
        with self.assertRaises(ValueError):
            IDEBridgeServer(bridge, host="0.0.0.0", port=0)

    def test_runtime_dispatches_authenticated_command(self):
        class FakeAdapter:
            kind = IDEKind.VS_CODE

            def capabilities(self):
                return frozenset({"insert_text"})

            def context(self):
                return None

            def execute(self, command):
                return IDECommandResult(ok=True, output={"command": command.kind.value}, metadata={})

        registry = IDEAdapterRegistry()
        registry.register(FakeAdapter())
        runtime = IDERuntime(registry)
        bridge = IDEBridge(policy=IDEBridgePolicy(token="secret"), runtime=runtime)
        server = IDEBridgeServer(bridge, host="127.0.0.1", port=0)
        server.start()
        try:
            body = json.dumps({
                "kind": "insert_text",
                "arguments": {"text": "hello"},
                "context": {"kind": "vs_code", "project_root": "/tmp/project"},
            }).encode()
            request = Request(
                f"http://127.0.0.1:{server.server.server_port}/v1/ide/command",
                data=body,
                headers={"Authorization": "Bearer secret", "Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                payload = json.loads(response.read())
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["result"]["ok"])
            self.assertEqual(payload["result"]["output"]["command"], "insert_text")
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()

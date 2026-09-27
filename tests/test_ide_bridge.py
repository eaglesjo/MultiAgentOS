import json
from urllib.request import Request, urlopen
import unittest

from core.contracts.ide import IDEEventKind, IDEKind
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


if __name__ == "__main__":
    unittest.main()

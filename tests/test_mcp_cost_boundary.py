import json
import tempfile
from pathlib import Path
from unittest import TestCase

from runtime.mcp.config import MCPConfigLoader

class MCPCostBoundaryTests(TestCase):
    def test_external_defaults_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); cfg=root/".multiagentos"; cfg.mkdir()
            (cfg/"mcp.json").write_text(json.dumps({"servers":{
                "paid":{"source":"external","transport":"streamable-http","endpoint":"https://example.invalid/mcp"}
            }}))
            spec=MCPConfigLoader().load(root)[0]
            self.assertFalse(spec.enabled)
            self.assertTrue(spec.requires_explicit_enable)
            self.assertEqual(spec.cost_policy,"external_service_possible")

    def test_builtin_defaults_enabled_without_external_billing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); cfg=root/".multiagentos"; cfg.mkdir()
            (cfg/"mcp.json").write_text(json.dumps({"servers":{
                "local":{"source":"built-in","command":"python"}
            }}))
            spec=MCPConfigLoader().load(root)[0]
            self.assertTrue(spec.enabled)
            self.assertFalse(spec.requires_explicit_enable)
            self.assertEqual(spec.cost_policy,"no_external_billing")

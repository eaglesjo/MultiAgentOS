import json
import tempfile
from pathlib import Path
from unittest import TestCase

from core.contracts.agent import AgentContract
from core.contracts.mcp import MCPTool, MCPToolProfile
from core.contracts.agent_execution_runtime_runtime import ToolSideEffect
from runtime.mcp.policy import MCPAuthorizationError, MCPToolAuthorizer, MCPToolProfileLoader


class MCPPolicyTests(TestCase):
    def test_profile_loader(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / ".multiagentos"
            config.mkdir()
            (config / "mcp-profiles.json").write_text(json.dumps({
                "profiles": {
                    "mobile-observer": {
                        "servers": ["mobile-mcp"],
                        "permissions": ["mcp.mobile.read"],
                        "side_effects": ["read"]
                    }
                }
            }))
            profiles = MCPToolProfileLoader().load(root)
            self.assertEqual(profiles[0].id, "mobile-observer")
            self.assertEqual(profiles[0].server_ids, frozenset({"mobile-mcp"}))

    def test_profile_denies_write_tool_to_observer(self):
        profile = MCPToolProfile(
            id="observer",
            server_ids=frozenset({"mobile-mcp"}),
            required_permissions=frozenset({"mcp.mobile.read"}),
            allowed_side_effects=frozenset({ToolSideEffect.READ}),
        )
        agent = AgentContract(
            id="mobile-observer",
            role="tester",
            permissions=frozenset({"mcp.mobile.read"}),
        )
        tool = MCPTool(
            name="tap",
            server_id="mobile-mcp",
            side_effect=ToolSideEffect.WRITE,
        )
        with self.assertRaises(MCPAuthorizationError):
            MCPToolAuthorizer((profile,)).authorize(agent, tool, "observer")

    def test_profile_allows_explicit_read_tool(self):
        profile = MCPToolProfile(
            id="observer",
            server_ids=frozenset({"mobile-mcp"}),
            allowed_tools=frozenset({"mobile-mcp:take_screenshot"}),
            required_permissions=frozenset({"mcp.mobile.read"}),
            allowed_side_effects=frozenset({ToolSideEffect.READ}),
        )
        agent = AgentContract(
            id="mobile-observer",
            role="tester",
            permissions=frozenset({"mcp.mobile.read"}),
        )
        tool = MCPTool(
            name="take_screenshot",
            server_id="mobile-mcp",
            side_effect=ToolSideEffect.READ,
        )
        MCPToolAuthorizer((profile,)).authorize(agent, tool, "observer")

import json, sys, tempfile
from pathlib import Path
from unittest import TestCase

from core.contracts.mcp import MCPToolCall
from runtime.mcp.client import MCPClient
from runtime.mcp.config import MCPConfigLoader

SERVER = r'''
import json, sys
for line in sys.stdin:
    req=json.loads(line)
    if "id" not in req:
        continue
    method=req["method"]
    if method=="initialize":
        result={"protocolVersion":"2025-03-26","capabilities":{"tools":{}},"serverInfo":{"name":"test","version":"1"}}
    elif method=="tools/list":
        result={"tools":[{"name":"ping","description":"Ping device","inputSchema":{"type":"object","properties":{}}}]}
    elif method=="tools/call":
        result={"content":[{"type":"text","text":"pong"}],"isError":False}
    else:
        result={}
    print(json.dumps({"jsonrpc":"2.0","id":req["id"],"result":result}), flush=True)
'''

class MCPRuntimeTests(TestCase):
    def test_config_loader_supports_mcp_server_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); cfg=root/".multiagentos"; cfg.mkdir()
            (cfg/"mcp.json").write_text(json.dumps({"servers":{
                "mobile-mcp":{"command":"npx","args":["-y","@mobilenext/mobile-mcp@latest"],
                              "metadata":{"provider":"mobile-next"}}
            }}))
            spec=MCPConfigLoader().load(root)[0]
            self.assertEqual(spec.id,"mobile-mcp")
            self.assertEqual(spec.command,("npx",))
            self.assertEqual(spec.args[0],"-y")

    def test_stdio_list_and_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            script=Path(tmp)/"server.py"; script.write_text(SERVER)
            client=MCPClient(__import__("core.contracts.mcp",fromlist=["MCPServerSpec"]).MCPServerSpec(
                id="test", command=(sys.executable,), args=(str(script),)))
            client.connect()
            try:
                tools=client.list_tools()
                self.assertEqual(tools[0].name,"ping")
                result=client.call_tool(MCPToolCall("test","ping"))
                self.assertFalse(result.is_error)
                self.assertEqual(result.content[0]["text"],"pong")
            finally:
                client.close()

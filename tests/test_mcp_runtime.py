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


    def test_streamable_http_session_and_tool_call(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                import json
                req=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                method=req["method"]
                if method=="initialize":
                    body={"jsonrpc":"2.0","id":req["id"],"result":{"protocolVersion":"2025-03-26","capabilities":{"tools":{}}}}
                    self.send_response(200); self.send_header("Content-Type","application/json")
                    self.send_header("Mcp-Session-Id","test-http-session"); self.end_headers()
                elif method=="notifications/initialized":
                    self.send_response(202); self.end_headers(); return
                elif method=="tools/list":
                    body={"jsonrpc":"2.0","id":req["id"],"result":{"tools":[{"name":"ping","inputSchema":{"type":"object"}}]}}
                    self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                else:
                    body={"jsonrpc":"2.0","id":req["id"],"result":{"content":[{"type":"text","text":"http-pong"}],"isError":False}}
                    self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                self.wfile.write(json.dumps(body).encode())
            def log_message(self,*args): pass
        server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        client=MCPClient(MCPServerSpec("http",transport="streamable-http",endpoint=f"http://127.0.0.1:{server.server_port}/mcp"))
        try:
            session=client.connect()
            self.assertEqual(session.id,"test-http-session")
            self.assertEqual(client.list_tools()[0].name,"ping")
            self.assertEqual(client.call_tool(MCPToolCall("http","ping")).content[0]["text"],"http-pong")
        finally:
            client.close(); server.shutdown(); server.server_close()

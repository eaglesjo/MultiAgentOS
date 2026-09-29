import tempfile
import unittest
from pathlib import Path
from core.contracts.mcp import MCPTool
from core.contracts.agent_execution_runtime_runtime import ToolRequest, ToolSideEffect
from runtime.repository_tools import GitToolBindings, MCPToolBindings
from runtime.policy import ExecutionPolicy
from runtime.tool_calling import ToolRuntime

class FakeGit:
    def status(self,cwd): return type("R",(),{"returncode":0,"stdout":"ok","stderr":""})()
    def diff(self,*a,**k): return type("R",(),{"returncode":0,"stdout":"diff","stderr":""})()
    def log(self,*a,**k): return type("R",(),{"returncode":0,"stdout":"log","stderr":""})()
    def add(self,*a,**k): return type("R",(),{"returncode":0,"stdout":"add","stderr":""})()
    def commit(self,*a,**k): return type("R",(),{"returncode":0,"stdout":"commit","stderr":""})()
    def push(self,*a,**k): return type("R",(),{"returncode":0,"stdout":"push","stderr":""})()

class FakeMCP:
    def list_tools(self): return (MCPTool("echo","Echo",{"type":"object"}, "local"),)
    def call_tool(self,call): return type("R",(),{"is_error":False,"content":("hello",),"raw":{"ok":True}})()

class RepositoryToolTests(unittest.TestCase):
    def test_git_tools_use_existing_git_runtime(self):
        with tempfile.TemporaryDirectory() as root:
            tools=ToolRuntime(ExecutionPolicy())
            GitToolBindings(root,tools,FakeGit())
            result=tools.execute(ToolRequest("git.status"))
            self.assertTrue(result.ok)
            self.assertEqual(result.output["stdout"],"ok")
            self.assertIn("git.commit",[s.id for s in tools.specs()])

    def test_mcp_tools_are_normalized(self):
        tools=ToolRuntime(ExecutionPolicy())
        binding=MCPToolBindings(tools,FakeMCP())
        self.assertEqual(binding.register_tools(),("mcp.local.echo",))
        result=tools.execute(ToolRequest("mcp.local.echo",{"value":"x"}))
        self.assertTrue(result.ok)
        self.assertEqual(result.output["content"],("hello",))

    def test_network_mcp_or_git_push_is_policy_blocked(self):
        tools=ToolRuntime(ExecutionPolicy(allow_network=False))
        spec=next(s for s in (GitToolBindings("/tmp",tools,FakeGit()).runtime.specs()) if s.id=="git.push")
        self.assertEqual(spec.side_effect,ToolSideEffect.NETWORK)

if __name__=="__main__":
    unittest.main()

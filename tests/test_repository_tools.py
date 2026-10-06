import tempfile
import unittest
from pathlib import Path
from core.contracts.mcp import MCPTool
from core.contracts.agent_execution_runtime import ToolRequest, ToolSideEffect
from runtime.repository_tools import GitHubToolBindings, GitToolBindings, MCPToolBindings
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



class FakeGitHubRuntime:
    def __init__(self):
        self.missions = []

    def run_actions_mission(self, mission):
        self.missions.append(mission)
        evidence = type(
            "Evidence",
            (),
            {
                "mission_id": mission.id,
                "run_id": 42,
                "status": "completed",
                "conclusion": "success",
                "source_sha": mission.source_sha,
                "head_sha": "main-tip-sha",
                "url": "https://example/run/42",
                "artifacts": ("execution-mission-evidence",),
                "logs_available": True,
                "disposition": type("Disposition", (), {"value": "succeeded"})(),
            },
        )()
        return type("Result", (), {"evidence": evidence})()


class GitHubMissionToolTests(unittest.TestCase):
    def test_github_actions_tool_can_resolve_source_sha_from_ref(self):
        class BranchResolvingGateway(FakeGitHubRuntime):
            class Gateway:
                def get_branch(self, repository, ref):
                    return type("Branch", (), {"sha": "0123456789abcdef0123456789abcdef01234567"})()
        github = FakeGitHubRuntime()
        github.gateway = BranchResolvingGateway.Gateway()
        tools = ToolRuntime(ExecutionPolicy(allow_github_actions=True))
        GitHubToolBindings(tools, github)
        result = tools.execute(
            ToolRequest(
                "github.actions.run_mission",
                {"repository": "owner/repo", "operation": "test"},
                work_unit_id="work-123",
            ),
            granted_permissions=frozenset({"github.actions"}),
        )
        self.assertTrue(result.ok, result.error)
        self.assertEqual(github.missions[0].source_sha, "0123456789abcdef0123456789abcdef01234567")

    def test_github_actions_tool_is_exposed(self):
        tools = ToolRuntime(ExecutionPolicy(allow_github_actions=True))
        github = FakeGitHubRuntime()
        GitHubToolBindings(tools, github)
        result = tools.execute(
            ToolRequest(
                "github.actions.run_mission",
                {
                    "repository": "owner/repo",
                    "source_sha": "0123456789abcdef0123456789abcdef01234567",
                    "operation": "test",
                },
                work_unit_id="work-123",
            ),
            granted_permissions=frozenset({"github.actions"}),
        )
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.output["mission_id"], "mission-work-123")
        self.assertEqual(github.missions[0].operation.value, "test")

    def test_github_actions_tool_is_policy_blocked_by_default(self):
        tools = ToolRuntime(ExecutionPolicy())
        GitHubToolBindings(tools, FakeGitHubRuntime())
        result = tools.execute(
            ToolRequest(
                "github.actions.run_mission",
                {
                    "repository": "owner/repo",
                    "source_sha": "0123456789abcdef0123456789abcdef01234567",
                    "operation": "test",
                },
                work_unit_id="work-123",
            ),
            granted_permissions=frozenset({"github.actions"}),
        )
        self.assertFalse(result.ok)
        self.assertIn("github.actions", result.error)


class ExecutionRouteToolTests(unittest.TestCase):
    def test_route_prefers_local(self):
        tools = ToolRuntime(ExecutionPolicy(allow_github_actions=True))
        GitHubToolBindings(tools, FakeGitHubRuntime())
        result = tools.execute(
            ToolRequest("execution.route.select", {"local_available": True}),
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.output["route"], "local")

    def test_route_falls_back_to_github_actions_after_local_failure(self):
        tools = ToolRuntime(ExecutionPolicy(allow_github_actions=True))
        GitHubToolBindings(tools, FakeGitHubRuntime())
        result = tools.execute(
            ToolRequest("execution.route.select", {"local_available": True, "local_failed": True}),
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.output["route"], "github_actions")

    def test_route_blocks_when_no_route_is_permitted(self):
        tools = ToolRuntime(ExecutionPolicy(allow_github_actions=False))
        GitHubToolBindings(tools, FakeGitHubRuntime())
        result = tools.execute(
            ToolRequest("execution.route.select", {"local_available": False}),
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.output["route"], "blocked")


if __name__=="__main__":
    unittest.main()

"""End-to-end project Chat Agent execution facade."""

from __future__ import annotations

from pathlib import Path

from core.chat_agent_bridge import ChatAgentExecutionResult, ChatAgentRequest
from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.execution import AgentExecutor, ResultReviewer, ResultVerifier
from runtime import AgentExecutionRuntime


def execute_project_chat_request(
    project_root: Path,
    request: ChatAgentRequest,
    *,
    agent: AgentContract,
    models: list[ModelSpec],
    executor: AgentExecutor,
    verifier: ResultVerifier | None = None,
    reviewer: ResultReviewer | None = None,
    chat_agent_id: str | None = None,
    preferred_model_ids: list[str] | None = None,
    routing_strategy: str = "pool",
) -> ChatAgentExecutionResult:
    """Resolve the configured Chat Agent and execute through the Agent Execution Runtime.

    The configured conversational provider supplies intent/plan; the supplied
    Agent Execution Runtime Agent/Model contracts own execution.
    """
    runtime = AgentExecutionRuntime()
    configured_agent, configured_model = runtime.project_chat_agent(project_root)
    adapter = runtime.project_chat_adapter(project_root)

    selected_chat_agent_id = chat_agent_id or configured_agent.id
    if configured_model and preferred_model_ids is None:
        preferred_model_ids = [configured_model]

    return runtime.execute_chat_request(
        request=request,
        adapter=adapter,
        agent=agent,
        models=models,
        executor=executor,
        chat_agent_id=selected_chat_agent_id,
        preferred_model_ids=preferred_model_ids,
        verifier=verifier,
        reviewer=reviewer,
        routing_strategy=routing_strategy,
        project_root=project_root,
    )



def execute_project_multi_agent_chat_request(
    project_root: Path,
    request: ChatAgentRequest,
    *,
    stages: list[AgentContract],
    models: list[ModelSpec],
    executor: AgentExecutor,
    verifier: ResultVerifier | None = None,
    reviewers=None,
    reviewer_runner=None,
    chat_agent_id: str | None = None,
    preferred_model_ids: list[str] | None = None,
    routing_strategy: str = "pool",
) -> ChatAgentExecutionResult:
    """Enter the Agent Execution Runtime multi-agent workflow from a project Chat Agent request."""
    runtime = AgentExecutionRuntime()
    configured_agent, configured_model = runtime.project_chat_agent(project_root)
    adapter = runtime.project_chat_adapter(project_root)
    selected_chat_agent_id = chat_agent_id or configured_agent.id
    if configured_model and preferred_model_ids is None:
        preferred_model_ids = [configured_model]
    return runtime.chat_agent_bridge().execute_workflow(
        request=request,
        adapter=adapter,
        stages=stages,
        models=models,
        executor=executor,
        chat_agent_id=selected_chat_agent_id,
        preferred_model_ids=preferred_model_ids,
        verifier=verifier,
        reviewers=reviewers,
        reviewer_runner=reviewer_runner,
        routing_strategy=routing_strategy,
        state_store=runtime.state_store(project_root),
        session_store=runtime.chat_session_store(project_root),
        artifact_store=runtime.artifact_store(project_root),
    )

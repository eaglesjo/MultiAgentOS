"""Native HTTP provider adapters for VYRELON Tool Calling."""
from __future__ import annotations
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any
from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelRequest, ModelResponse
from core.contracts.vyrelon_runtime import ToolSpec
from runtime.policy import ExecutionPolicy

def _tool_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)[:64] or "tool"

def _tool_defs(tools: tuple[ToolSpec, ...]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    aliases, used, out = {}, set(), []
    for tool in tools:
        alias, base = _tool_name(tool.id), _tool_name(tool.id)
        index = 2
        while alias in used:
            alias = f"{base}_{index}"
            index += 1
        used.add(alias)
        aliases[alias] = tool.id
        out.append({"name": alias, "description": tool.description, "parameters": tool.input_schema or {"type": "object", "properties": {}}})
    return out, aliases

def _request(endpoint: str, payload: dict[str, Any], headers: dict[str, str], policy: ExecutionPolicy) -> dict[str, Any]:
    if not policy.permits("network"):
        raise PermissionError("Network model execution is disabled by policy")
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=300) as response:
        data = json.loads(response.read().decode())
    if not isinstance(data, dict):
        raise ValueError("provider response must be a JSON object")
    return data

@dataclass(frozen=True)
class OpenAIResponsesToolAdapter:
    api_key_env: str = "OPENAI_API_KEY"
    endpoint: str = "https://api.openai.com/v1/responses"
    policy: ExecutionPolicy = ExecutionPolicy(allow_network=True)
    def generate(self, model: ModelSpec, request: ModelRequest) -> ModelResponse:
        return self._generate(model, request, ())
    def generate_with_tools(self, model: ModelSpec, request: ModelRequest, tools: tuple[ToolSpec, ...]) -> ModelResponse:
        return self._generate(model, request, tools)
    def _generate(self, model: ModelSpec, request: ModelRequest, tools: tuple[ToolSpec, ...]) -> ModelResponse:
        key = os.environ.get(self.api_key_env)
        if not key: raise RuntimeError(f"Required model credential environment variable is missing: {self.api_key_env}")
        definitions, aliases = _tool_defs(tools)
        input_items: list[dict[str, Any]] = [{"role": "user", "content": request.prompt}]
        history = request.metadata.get("tool_history", ())
        for turn in history if isinstance(history, (list, tuple)) else ():
            for call in turn.get("tool_calls", ()):
                input_items.append({"type": "function_call", "call_id": call["call_id"], "name": _tool_name(str(call["tool_id"])), "arguments": json.dumps(call["arguments"])})
            for result in turn.get("tool_results", ()):
                input_items.append({"type": "function_call_output", "call_id": result["call_id"], "output": json.dumps(result.get("output")) if result.get("ok") else json.dumps({"error": result.get("error")})})
        payload: dict[str, Any] = {"model": model.id, "input": input_items}
        if request.system: payload["instructions"] = request.system
        if definitions: payload["tools"] = [{"type": "function", "name": d["name"], "description": d["description"], "parameters": d["parameters"]} for d in definitions]
        data = _request(self.endpoint, payload, {"Authorization": f"Bearer {key}"}, self.policy)
        calls, texts = [], []
        for item in data.get("output", ()):
            if item.get("type") == "function_call":
                calls.append({"id": item.get("call_id", item.get("id")), "name": aliases.get(item.get("name"), item.get("name")), "arguments": json.loads(item.get("arguments", "{}"))})
            elif item.get("type") == "message":
                texts.extend(part.get("text", "") for part in item.get("content", ()) if part.get("type") == "output_text")
        return ModelResponse("".join(texts), model.id, {"adapter": "openai_responses", "tool_calls": calls, "provider_response_id": data.get("id")})

@dataclass(frozen=True)
class AnthropicMessagesToolAdapter:
    api_key_env: str = "ANTHROPIC_API_KEY"
    endpoint: str = "https://api.anthropic.com/v1/messages"
    api_version: str = "2023-06-01"
    max_tokens: int = 4096
    policy: ExecutionPolicy = ExecutionPolicy(allow_network=True)
    def generate(self, model: ModelSpec, request: ModelRequest) -> ModelResponse:
        return self._generate(model, request, ())
    def generate_with_tools(self, model: ModelSpec, request: ModelRequest, tools: tuple[ToolSpec, ...]) -> ModelResponse:
        return self._generate(model, request, tools)
    def _generate(self, model: ModelSpec, request: ModelRequest, tools: tuple[ToolSpec, ...]) -> ModelResponse:
        key = os.environ.get(self.api_key_env)
        if not key: raise RuntimeError(f"Required model credential environment variable is missing: {self.api_key_env}")
        definitions, aliases = _tool_defs(tools)
        messages: list[dict[str, Any]] = [{"role": "user", "content": request.prompt}]
        history = request.metadata.get("tool_history", ())
        for turn in history if isinstance(history, (list, tuple)) else ():
            assistant = [{"type": "tool_use", "id": c["call_id"], "name": _tool_name(str(c["tool_id"])), "input": c["arguments"]} for c in turn.get("tool_calls", ())]
            if assistant: messages.append({"role": "assistant", "content": assistant})
            results = [{"type": "tool_result", "tool_use_id": r["call_id"], "content": json.dumps(r.get("output")) if r.get("ok") else json.dumps({"error": r.get("error")}), "is_error": not r.get("ok", False)} for r in turn.get("tool_results", ())]
            if results: messages.append({"role": "user", "content": results})
        payload: dict[str, Any] = {"model": model.id, "max_tokens": self.max_tokens, "messages": messages}
        if request.system: payload["system"] = request.system
        if definitions: payload["tools"] = [{"name": d["name"], "description": d["description"], "input_schema": d["parameters"]} for d in definitions]
        data = _request(self.endpoint, payload, {"x-api-key": key, "anthropic-version": self.api_version}, self.policy)
        calls, texts = [], []
        for block in data.get("content", ()):
            if block.get("type") == "tool_use": calls.append({"id": block["id"], "name": aliases.get(block["name"], block["name"]), "arguments": block.get("input", {})})
            elif block.get("type") == "text": texts.append(block.get("text", ""))
        return ModelResponse("".join(texts), model.id, {"adapter": "anthropic_messages", "tool_calls": calls, "stop_reason": data.get("stop_reason")})

@dataclass(frozen=True)
class GeminiGenerateContentToolAdapter:
    api_key_env: str = "GEMINI_API_KEY"
    endpoint_base: str = "https://generativelanguage.googleapis.com/v1beta/models"
    policy: ExecutionPolicy = ExecutionPolicy(allow_network=True)
    def generate(self, model: ModelSpec, request: ModelRequest) -> ModelResponse:
        return self._generate(model, request, ())
    def generate_with_tools(self, model: ModelSpec, request: ModelRequest, tools: tuple[ToolSpec, ...]) -> ModelResponse:
        return self._generate(model, request, tools)
    def _generate(self, model: ModelSpec, request: ModelRequest, tools: tuple[ToolSpec, ...]) -> ModelResponse:
        key = os.environ.get(self.api_key_env)
        if not key: raise RuntimeError(f"Required model credential environment variable is missing: {self.api_key_env}")
        definitions, aliases = _tool_defs(tools)
        contents: list[dict[str, Any]] = [{"role": "user", "parts": [{"text": request.prompt}]}]
        history = request.metadata.get("tool_history", ())
        for turn in history if isinstance(history, (list, tuple)) else ():
            calls = [{"functionCall": {"name": _tool_name(str(c["tool_id"])), "args": c["arguments"]}} for c in turn.get("tool_calls", ())]
            if calls: contents.append({"role": "model", "parts": calls})
            results = [{"functionResponse": {"name": _tool_name(str(r["tool_id"])), "response": {"ok": r.get("ok"), "output": r.get("output"), "error": r.get("error")}}} for r in turn.get("tool_results", ())]
            if results: contents.append({"role": "user", "parts": results})
        payload: dict[str, Any] = {"contents": contents}
        if request.system: payload["systemInstruction"] = {"parts": [{"text": request.system}]}
        if definitions: payload["tools"] = [{"functionDeclarations": [{"name": d["name"], "description": d["description"], "parameters": d["parameters"]} for d in definitions]}]
        endpoint = f"{self.endpoint_base}/{urllib.parse.quote(model.id, safe='')}:generateContent?key={urllib.parse.quote(key, safe='')}"
        data = _request(endpoint, payload, {}, self.policy)
        calls, texts = [], []
        for candidate in data.get("candidates", ()):
            for part in candidate.get("content", {}).get("parts", ()):
                if "functionCall" in part:
                    fc = part["functionCall"]; calls.append({"id": fc.get("id", f"call-{len(calls)+1}"), "name": aliases.get(fc.get("name"), fc.get("name")), "arguments": fc.get("args", {})})
                elif "text" in part: texts.append(part["text"])
        return ModelResponse("".join(texts), model.id, {"adapter": "gemini_generate_content", "tool_calls": calls})

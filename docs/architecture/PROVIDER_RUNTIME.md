# Declarative Provider Runtime

Agent Execution Runtime keeps provider configuration separate from provider execution.

Example:

```json
{
  "providers": [
    {
      "id": "openai",
      "kind": "openai",
      "metadata": {
        "api_key_env": "OPENAI_API_KEY"
      },
      "models": [
        {
          "id": "gpt-model",
          "capabilities": ["tool_calling"],
          "metadata": {
            "adapter_id": "openai"
          }
        }
      ]
    }
  ]
}
```

The runtime path is:

```
providers.json
  -> ProviderConfigLoader
  -> AIProviderRegistry
  -> NativeProviderMaterializer
  -> ModelAdapterRegistry
  -> ModelAgentExecutor
  -> ToolCallingRuntime
```

Supported native kinds:

- `openai` / `openai_responses`
- `anthropic` / `anthropic_messages`
- `gemini` / `gemini_generate_content`

Network execution remains disabled unless the caller supplies an
`ExecutionPolicy(allow_network=True)`. Credentials are read from environment
variables and are never persisted by the provider runtime.

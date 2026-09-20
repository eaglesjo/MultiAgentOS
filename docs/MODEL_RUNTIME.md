# VYRELON Model Runtime

The model runtime separates model identity from the mechanism used to invoke it.

## Contracts

- ModelSpec identifies the selected model and provider.
- ModelRequest carries the prompt and optional system context.
- ModelResponse contains normalized model output.
- ModelAdapter is the provider-neutral invocation boundary.
- ModelAdapterRegistry maps adapter IDs to implementations.
- ModelInvoker resolves the adapter and performs the invocation.

A ModelSpec can declare an adapter_id in metadata. If it does not, provider_id is used as the adapter key.

## Generic CLI support

CLIModelAdapter accepts an explicit argv command. This means VYRELON can integrate with any AI product that exposes a command-line interface without making that product a special case in the core.

Examples include hosted AI CLIs, local model CLIs, custom organization agents, and future IDE or remote bridges.

Credentials are inherited from the host environment or the CLI's own authentication mechanism. They are never stored in ModelSpec or repository files.

## Extension points

The same ModelAdapter contract can later support:

- direct HTTP/API providers
- MCP-backed model gateways
- local inference servers
- remote model services
- IDE agent bridges

The orchestration layer remains unchanged when a new adapter is added.

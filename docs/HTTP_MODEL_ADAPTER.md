# VYRELON HTTP Model Adapter

HTTPModelAdapter provides a generic JSON-over-HTTP integration point.

It is intentionally not an OpenAI, Anthropic, Google, or other vendor-specific client. A configured endpoint, request template, response path, and credential environment variables are enough to integrate an HTTP model service.

Credentials are referenced by environment-variable names and are never stored in repository configuration.

Network access is policy-controlled. The adapter is disabled when ExecutionPolicy does not permit network access.

This supports OpenAI-compatible endpoints, local inference servers, self-hosted gateways, and custom model services when their request/response shapes can be expressed by the template and response path.

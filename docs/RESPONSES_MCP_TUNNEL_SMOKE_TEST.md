# Responses API → Secure MCP Tunnel smoke test

This is the smallest end-to-end validation for the MultiAgentOS local MCP runtime through OpenAI's Secure MCP Tunnel.

The path under test is:

```text
Responses API
  -> MCP tool
  -> Secure MCP Tunnel (tunnel_id)
  -> tunnel-client
  -> MultiAgentOS Streamable HTTP MCP
  -> filesystem.write / filesystem.read
```

OpenAI documents `tunnel_id` as the Responses API mechanism for connecting a private/local MCP server through Secure MCP Tunnel. The tunnel client must remain running while the request is tested.

## Prerequisites

- MultiAgentOS MCP server is running.
- `tunnel-client` is running and healthy.
- The tunnel is associated with the OpenAI Platform organization used by the API key.
- A dedicated API key is available in `MULTIAGENTOS_OPENAI_API_KEY`.
- The tunnel ID is available in `MULTIAGENTOS_TUNNEL_ID`.

Do not replace an unrelated `OPENAI_API_KEY` just for this test.

## Run

From the MultiAgentOS checkout:

```bash
export MULTIAGENTOS_OPENAI_API_KEY='...'
export MULTIAGENTOS_TUNNEL_ID='tunnel_...'

python3 scripts/verify_responses_mcp_tunnel.py
```

Optional model override:

```bash
export MULTIAGENTOS_OPENAI_MODEL='gpt-5'
python3 scripts/verify_responses_mcp_tunnel.py
```

The script asks the model to actually call:

1. `filesystem.write` for `MCP_TUNNEL_TEST.md`
2. `filesystem.read` for the same file

It checks that both MCP calls were returned and that the expected read-back content is present. The API key itself is never printed.

## Cleanup

The MCP runtime intentionally has no delete tool in its default tool surface, so the smoke test leaves one small test file behind:

```bash
rm -f MCP_TUNNEL_TEST.md
```

This is deliberate: a successful test proves that the remote API path could perform a real write, rather than only discovering the MCP tool schema.

## Troubleshooting

If no `filesystem.write` call is observed, check the running tunnel client and tunnel association first. OpenAI's current Secure MCP Tunnel documentation also recommends checking the tunnel client's health/readiness and keeping the client running during MCP testing.

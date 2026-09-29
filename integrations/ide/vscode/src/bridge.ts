import type { IDECommand, IDECommandResult, IDEContext, IDEEvent } from "./contracts";

export class AgentExecutionRuntimeBridge {
  constructor(
    private readonly endpoint: string,
    private readonly token?: string,
  ) {}

  private headers(): HeadersInit {
    const headers: Record<string, string> = {
      "content-type": "application/json",
    };
    if (this.token) headers.authorization = `Bearer ${this.token}`;
    return headers;
  }

  async getContext(context: IDEContext): Promise<IDEContext> {
    const event: IDEEvent = {
      kind: "context_changed",
      context,
      payload: {},
      metadata: { source: "vscode" },
    };
    const response = await fetch(`${this.endpoint}/v1/ide/event`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(event),
    });
    if (!response.ok) {
      throw new Error(`Agent Execution Runtime event request failed: ${response.status}`);
    }
    const envelope = (await response.json()) as { result?: { context?: IDEContext } };
    return envelope.result?.context ?? context;
  }

  async execute(command: IDECommand): Promise<IDECommandResult> {
    const response = await fetch(`${this.endpoint}/v1/ide/command`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(command),
    });
    if (!response.ok) {
      throw new Error(`Agent Execution Runtime command failed: ${response.status}`);
    }
    const envelope = (await response.json()) as { result?: IDECommandResult };
    return envelope.result ?? { ok: false, error: "Agent Execution Runtime returned no command result.", metadata: {} };
  }
}
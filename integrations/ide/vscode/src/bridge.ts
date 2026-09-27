import type { IDECommand, IDECommandResult, IDEContext } from "./contracts";

export class VyrelonBridge {
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
    const response = await fetch(`${this.endpoint}/v1/ide/context`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(context),
    });
    if (!response.ok) {
      throw new Error(`VYRELON context request failed: ${response.status}`);
    }
    return (await response.json()) as IDEContext;
  }

  async execute(command: IDECommand): Promise<IDECommandResult> {
    const response = await fetch(`${this.endpoint}/v1/ide/command`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(command),
    });
    if (!response.ok) {
      throw new Error(`VYRELON command failed: ${response.status}`);
    }
    return (await response.json()) as IDECommandResult;
  }
}
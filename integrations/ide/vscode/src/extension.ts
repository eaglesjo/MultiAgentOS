import * as vscode from "vscode";
import type { IDECommand, IDEContext } from "./contracts";
import { AgentExecutionRuntimeBridge } from "./bridge";

function workspaceRoot(): string {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? "";
}

function activeContext(): IDEContext {
  const editor = vscode.window.activeTextEditor;
  const selection = editor?.selection;
  return {
    kind: "vs_code",
    project_root: workspaceRoot(),
    workspace_id: vscode.workspace.name,
    file_path: editor?.document.uri.fsPath,
    selection_start: selection?.start.translate(0, 0).line,
    selection_end: selection?.end.translate(0, 0).line,
    language_id: editor?.document.languageId,
    metadata: {
      uri: editor?.document.uri.toString(),
    },
  };
}

function bridge(): AgentExecutionRuntimeBridge {
  const config = vscode.workspace.getConfiguration("agentExecutionRuntime");
  const endpoint = config.get<string>("endpoint", "http://127.0.0.1:8787").replace(/\/$/, "");
  const token = config.get<string>("token", "");
  return new AgentExecutionRuntimeBridge(endpoint, token);
}

export function activate(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("agentExecutionRuntime.showContext", async () => {
      try {
        const current = activeContext();
        const normalized = await bridge().getContext(current);
        const file = normalized.file_path ?? "(no active file)";
        vscode.window.showInformationMessage(
          `Agent Execution Runtime: ${file} [${normalized.language_id ?? "unknown"}]`,
        );
      } catch (error) {
        vscode.window.showErrorMessage(String(error));
      }
    }),
    vscode.commands.registerCommand("agentExecutionRuntime.sendSelection", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor || editor.selection.isEmpty) {
        vscode.window.showWarningMessage("Agent Execution Runtime: select text first.");
        return;
      }

      const current = activeContext();
      const command: IDECommand = {
        kind: "insert_text",
        arguments: {
          text: editor.document.getText(editor.selection),
        },
        context: current,
        metadata: { source: "vscode.selection" },
      };

      try {
        const result = await bridge().execute(command);
        if (!result.ok) {
          throw new Error(result.error ?? "Agent Execution Runtime rejected the command.");
        }
        vscode.window.showInformationMessage("Agent Execution Runtime: selection sent.");
      } catch (error) {
        vscode.window.showErrorMessage(String(error));
      }
    }),
  );
}

export function deactivate(): void {}

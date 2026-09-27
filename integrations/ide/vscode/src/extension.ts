import * as vscode from "vscode";
import type { IDECommand, IDEContext } from "./contracts";
import { VyrelonBridge } from "./bridge";

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

function bridge(): VyrelonBridge {
  const config = vscode.workspace.getConfiguration("vyrelon");
  const endpoint = config.get<string>("endpoint", "http://127.0.0.1:8787").replace(/\/$/, "");
  const token = config.get<string>("token", "");
  return new VyrelonBridge(endpoint, token);
}

export function activate(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("vyrelon.showContext", async () => {
      try {
        const current = activeContext();
        const normalized = await bridge().getContext(current);
        const file = normalized.file_path ?? "(no active file)";
        vscode.window.showInformationMessage(
          `VYRELON: ${file} [${normalized.language_id ?? "unknown"}]`,
        );
      } catch (error) {
        vscode.window.showErrorMessage(String(error));
      }
    }),
    vscode.commands.registerCommand("vyrelon.sendSelection", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor || editor.selection.isEmpty) {
        vscode.window.showWarningMessage("VYRELON: select text first.");
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
          throw new Error(result.error ?? "VYRELON rejected the command.");
        }
        vscode.window.showInformationMessage("VYRELON: selection sent.");
      } catch (error) {
        vscode.window.showErrorMessage(String(error));
      }
    }),
  );
}

export function deactivate(): void {}

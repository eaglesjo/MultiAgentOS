export type IDEEventKind =
  | "context_changed"
  | "selection_changed"
  | "file_opened"
  | "file_saved"
  | "workspace_opened";

export type IDECommandKind =
  | "open_workspace"
  | "open_file"
  | "insert_text"
  | "replace_selection"
  | "run_command"
  | "show_message"
  | "show_diff";

export interface IDEContext {
  kind: "vs_code";
  project_root: string;
  workspace_id?: string;
  file_path?: string;
  selection_start?: number;
  selection_end?: number;
  language_id?: string;
  metadata: Record<string, unknown>;
}

export interface IDEEvent {
  kind: IDEEventKind;
  context: IDEContext;
  payload: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export interface IDECommand {
  kind: IDECommandKind;
  arguments: Record<string, unknown>;
  context?: IDEContext;
  metadata: Record<string, unknown>;
}

export interface IDECommandResult {
  ok: boolean;
  output?: unknown;
  error?: string;
  metadata: Record<string, unknown>;
}
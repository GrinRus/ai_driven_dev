export type BridgeEvent = "userprompt" | "pretooluse" | "stop" | "subagent_stop";

export interface HookSpecificOutput {
  hookEventName?: string;
  permissionDecision?: string;
  permissionDecisionReason?: string;
  updatedInput?: Record<string, unknown>;
}

export interface BridgePayload {
  status?: string;
  decision?: string;
  reason?: string;
  systemMessage?: string;
  hookSpecificOutput?: HookSpecificOutput;
  failed_hook?: string;
}

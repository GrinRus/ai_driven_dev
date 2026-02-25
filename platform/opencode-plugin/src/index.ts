import { bridgeBlockReason, bridgeUpdatedInput, callBridge } from "./bridge.js";
import type { BridgeEvent } from "./types.js";

type HookEnvelope = {
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
};

function basePayload(envelope: HookEnvelope, hookEventName: string): Record<string, unknown> {
  const output = envelope.output || {};
  return {
    hook_event_name: hookEventName,
    cwd: process.cwd(),
    session_id: String(output.session_id || output.sessionId || output.sessionID || ""),
    transcript_path: String(output.transcript_path || output.transcriptPath || ""),
    permission_mode: String(output.permission_mode || output.permissionMode || ""),
  };
}

function runBridge(event: BridgeEvent, payload: Record<string, unknown>): void {
  const result = callBridge(event, payload);
  const reason = bridgeBlockReason(result);
  if (reason) {
    throw new Error(reason);
  }
}

const plugin = {
  name: "feature-dev-aidd-opencode-bridge",
  hooks: {
    "chat.message"(envelope: HookEnvelope): HookEnvelope {
      const payload = basePayload(envelope, "UserPromptSubmit");
      const output = envelope.output || {};
      if (typeof output.message === "string" && output.message.trim()) {
        payload.message = output.message;
      }
      runBridge("userprompt", payload);
      return envelope;
    },
    "tool.execute.before"(envelope: HookEnvelope): HookEnvelope {
      const output = envelope.output || {};
      const toolName = String(
        (output.tool as { name?: string } | undefined)?.name || output.name || output.tool_name || "unknown",
      );
      const args =
        output.args && typeof output.args === "object" ? (output.args as Record<string, unknown>) : {};
      const payload = basePayload(envelope, "PreToolUse");
      payload.tool_name = toolName;
      payload.tool_input = args;
      const result = callBridge("pretooluse", payload);
      const reason = bridgeBlockReason(result);
      if (reason) {
        throw new Error(reason);
      }
      const updated = bridgeUpdatedInput(result);
      if (!updated) {
        return envelope;
      }
      return {
        ...envelope,
        output: {
          ...output,
          args: updated,
        },
      };
    },
    event(envelope: HookEnvelope): HookEnvelope {
      const eventType = String((envelope.input || {}).type || "").toLowerCase();
      if (eventType === "session.idle" || eventType === "session.compacted") {
        runBridge("stop", basePayload(envelope, "Stop"));
      }
      return envelope;
    },
    "permission.ask"(envelope: HookEnvelope): HookEnvelope {
      return envelope;
    },
  },
};

export default plugin;

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { BridgeEvent, BridgePayload } from "./types.js";

const FILE_DIR = path.dirname(fileURLToPath(import.meta.url));

function resolvePluginRoot(): string {
  const envCandidates = [process.env.AIDD_PLUGIN_ROOT, process.env.CLAUDE_PLUGIN_ROOT];
  for (const candidate of envCandidates) {
    const value = String(candidate || "").trim();
    if (value) {
      return value;
    }
  }
  return path.resolve(FILE_DIR, "../../..");
}

function resolveBridgeScript(pluginRoot: string): string {
  return path.join(pluginRoot, "hooks", "opencode_bridge.py");
}

export function callBridge(event: BridgeEvent, payload: Record<string, unknown>): BridgePayload {
  const pluginRoot = resolvePluginRoot();
  const bridgeScript = resolveBridgeScript(pluginRoot);
  if (!fs.existsSync(bridgeScript)) {
    throw new Error(
      [
        `bridge script not found: ${bridgeScript}`,
        "Set AIDD_PLUGIN_ROOT (or CLAUDE_PLUGIN_ROOT) to your ai_driven_dev repository root.",
      ].join(" "),
    );
  }
  const proc = spawnSync("python3", [bridgeScript, "--event", event], {
    input: JSON.stringify(payload),
    encoding: "utf8",
    env: {
      ...process.env,
      CLAUDE_PLUGIN_ROOT: pluginRoot,
    },
  });
  if (proc.error) {
    throw proc.error;
  }
  if ((proc.status ?? 1) !== 0) {
    const stderr = String(proc.stderr || "").trim();
    const stdout = String(proc.stdout || "").trim();
    throw new Error(stderr || stdout || `bridge failed for event=${event}`);
  }
  const output = String(proc.stdout || "").trim();
  if (!output) {
    return {};
  }
  const parsed = JSON.parse(output);
  return typeof parsed === "object" && parsed !== null ? (parsed as BridgePayload) : {};
}

export function bridgeBlockReason(payload: BridgePayload): string {
  const decision = String(payload.decision || "").toLowerCase();
  if (decision === "block") {
    return String(payload.reason || payload.systemMessage || "bridge blocked UserPromptSubmit");
  }
  const permission = String(payload.hookSpecificOutput?.permissionDecision || "").toLowerCase();
  if (permission === "deny" || permission === "ask") {
    return String(
      payload.hookSpecificOutput?.permissionDecisionReason ||
        payload.reason ||
        payload.systemMessage ||
        `bridge blocked PreToolUse (${permission})`,
    );
  }
  if (String(payload.status || "").toLowerCase() === "error") {
    return String(payload.reason || payload.systemMessage || payload.failed_hook || "bridge execution failed");
  }
  return "";
}

export function bridgeUpdatedInput(payload: BridgePayload): Record<string, unknown> | null {
  const updated = payload.hookSpecificOutput?.updatedInput;
  if (!updated || typeof updated !== "object") {
    return null;
  }
  return updated;
}

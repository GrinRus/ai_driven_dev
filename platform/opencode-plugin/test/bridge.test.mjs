import test from "node:test";
import assert from "node:assert/strict";
import { bridgeBlockReason, bridgeUpdatedInput, callBridge } from "../dist/bridge.js";

test("bridgeBlockReason returns reason for decision=block", () => {
  const reason = bridgeBlockReason({
    decision: "block",
    reason: "Context GC blocked prompt",
  });
  assert.equal(reason, "Context GC blocked prompt");
});

test("bridgeBlockReason returns reason for permission deny", () => {
  const reason = bridgeBlockReason({
    hookSpecificOutput: {
      permissionDecision: "deny",
      permissionDecisionReason: "Read outside writemap",
    },
  });
  assert.equal(reason, "Read outside writemap");
});

test("bridgeUpdatedInput extracts updatedInput payload", () => {
  const updated = bridgeUpdatedInput({
    hookSpecificOutput: {
      updatedInput: {
        command: "echo wrapped",
      },
    },
  });
  assert.deepEqual(updated, { command: "echo wrapped" });
});

test("callBridge fails fast with clear message when bridge script path is invalid", () => {
  const previous = process.env.AIDD_PLUGIN_ROOT;
  process.env.AIDD_PLUGIN_ROOT = "/tmp/aidd-opencode-missing-root";
  try {
    assert.throws(
      () => callBridge("userprompt", {}),
      /bridge script not found/,
    );
  } finally {
    if (typeof previous === "string") {
      process.env.AIDD_PLUGIN_ROOT = previous;
    } else {
      delete process.env.AIDD_PLUGIN_ROOT;
    }
  }
});

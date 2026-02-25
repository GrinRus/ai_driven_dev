from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT


BRIDGE_SCRIPT = REPO_ROOT / "hooks" / "opencode_bridge.py"


def _write_script(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


class OpenCodeBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="opencode-bridge-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))
        self.plugin_root = self.tmpdir / "plugin"
        (self.plugin_root / "hooks").mkdir(parents=True, exist_ok=True)

    def _run_bridge(
        self,
        event: str,
        payload: dict,
        *,
        extra_env: dict | None = None,
        set_claude_root: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        if set_claude_root:
            env["CLAUDE_PLUGIN_ROOT"] = str(self.plugin_root)
        else:
            env.pop("CLAUDE_PLUGIN_ROOT", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["python3", str(BRIDGE_SCRIPT), "--event", event],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=env,
            cwd=self.tmpdir,
        )

    def test_userprompt_block_passthrough(self) -> None:
        _write_script(
            self.plugin_root / "hooks" / "context-gc-userprompt.sh",
            "#!/usr/bin/env bash\ncat >/dev/null\necho '{\"decision\":\"block\",\"reason\":\"blocked-by-policy\"}'\n",
        )
        payload = {"cwd": str(self.tmpdir), "hook_event_name": "UserPromptSubmit"}
        result = self._run_bridge("userprompt", payload)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        body = json.loads(result.stdout)
        self.assertEqual(body.get("decision"), "block")
        self.assertEqual(body.get("reason"), "blocked-by-policy")

    def test_pretooluse_updated_input_passthrough(self) -> None:
        _write_script(
            self.plugin_root / "hooks" / "context-gc-pretooluse.sh",
            (
                "#!/usr/bin/env bash\n"
                "cat >/dev/null\n"
                "echo '{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\","
                "\"permissionDecision\":\"allow\",\"updatedInput\":{\"command\":\"echo wrapped\"}}}'\n"
            ),
        )
        payload = {"cwd": str(self.tmpdir), "hook_event_name": "PreToolUse"}
        result = self._run_bridge("pretooluse", payload)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        body = json.loads(result.stdout)
        hook = body.get("hookSpecificOutput") or {}
        self.assertEqual(hook.get("permissionDecision"), "allow")
        self.assertEqual((hook.get("updatedInput") or {}).get("command"), "echo wrapped")

    def test_aidd_plugin_root_env_alias_supported(self) -> None:
        _write_script(
            self.plugin_root / "hooks" / "context-gc-userprompt.sh",
            "#!/usr/bin/env bash\ncat >/dev/null\necho '{\"decision\":\"allow\"}'\n",
        )
        payload = {"cwd": str(self.tmpdir), "hook_event_name": "UserPromptSubmit"}
        result = self._run_bridge(
            "userprompt",
            payload,
            set_claude_root=False,
            extra_env={"AIDD_PLUGIN_ROOT": str(self.plugin_root)},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        body = json.loads(result.stdout)
        self.assertEqual(body.get("decision"), "allow")

    def test_stop_runs_hook_chain_in_order(self) -> None:
        log_path = self.tmpdir / "stop-chain.log"
        script = (
            "#!/usr/bin/env bash\n"
            "cat >/dev/null\n"
            "echo \"$HOOK_NAME\" >> \"$LOG_PATH\"\n"
            "echo '{}'\n"
        )
        for hook in (
            "context-gc-stop.sh",
            "gate-workflow.sh",
            "gate-tests.sh",
            "gate-qa.sh",
            "format-and-test.sh",
            "lint-deps.sh",
        ):
            _write_script(
                self.plugin_root / "hooks" / hook,
                f"#!/usr/bin/env bash\nHOOK_NAME={hook!r}\n{script}",
            )
        payload = {"cwd": str(self.tmpdir), "hook_event_name": "Stop"}
        result = self._run_bridge(
            "stop",
            payload,
            extra_env={"LOG_PATH": str(log_path)},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        body = json.loads(result.stdout)
        self.assertEqual(body.get("status"), "ok")
        self.assertEqual([item.get("hook") for item in body.get("results", [])], [
            "context-gc-stop.sh",
            "gate-workflow.sh",
            "gate-tests.sh",
            "gate-qa.sh",
            "format-and-test.sh",
            "lint-deps.sh",
        ])


if __name__ == "__main__":
    unittest.main()

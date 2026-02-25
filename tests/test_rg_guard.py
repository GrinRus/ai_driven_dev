import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT, ensure_project_root, write_active_state, write_json

HOOK_SCRIPT = REPO_ROOT / "hooks" / "context-gc-pretooluse.sh"


def _run_pretool(root: Path, payload: dict, *, hooks_mode: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
    env["AIDD_CONTEXT_GC"] = "full"
    env["AIDD_HOOKS_MODE"] = hooks_mode
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [str(HOOK_SCRIPT)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=root,
        env=env,
    )


def _write_maps(root: Path, ticket: str, scope_key: str, work_item_key: str) -> None:
    write_json(
        root,
        f"reports/context/{ticket}/{scope_key}.readmap.json",
        {
            "schema": "aidd.readmap.v1",
            "ticket": ticket,
            "stage": "implement",
            "scope_key": scope_key,
            "work_item_key": work_item_key,
            "generated_at": "2026-02-25T00:00:00Z",
            "entries": [],
            "allowed_paths": ["src/**"],
            "loop_allowed_paths": [],
        },
    )
    write_json(
        root,
        f"reports/context/{ticket}/{scope_key}.writemap.json",
        {
            "schema": "aidd.writemap.v1",
            "ticket": ticket,
            "stage": "implement",
            "scope_key": scope_key,
            "work_item_key": work_item_key,
            "generated_at": "2026-02-25T00:00:00Z",
            "allowed_paths": ["src/**"],
            "loop_allowed_paths": [],
            "docops_only_paths": [],
            "always_allow": ["aidd/reports/**", "aidd/reports/actions/**"],
        },
    )


class RgGuardTests(unittest.TestCase):
    def test_strict_denies_rg_without_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rg-guard-deny-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "RG-GUARD-1"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_key)
            _write_maps(root, ticket, scope_key, work_item_key)
            write_json(
                root,
                "config/gates.json",
                {
                    "memory": {
                        "slice_enforcement": "warn",
                        "enforce_stages": ["implement"],
                        "rg_policy": "controlled_fallback",
                        "max_slice_age_minutes": 240,
                    }
                },
            )
            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "rg TODO src"},
            }
            result = _run_pretool(root, payload, hooks_mode="strict")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            hook_output = data.get("hookSpecificOutput", {})
            self.assertEqual(hook_output.get("permissionDecision"), "deny")
            reason = str(hook_output.get("permissionDecisionReason") or "")
            self.assertIn("rg_without_slice", reason)

    def test_fast_asks_rg_without_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rg-guard-ask-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "RG-GUARD-2"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_key)
            _write_maps(root, ticket, scope_key, work_item_key)
            write_json(
                root,
                "config/gates.json",
                {
                    "memory": {
                        "slice_enforcement": "warn",
                        "enforce_stages": ["implement"],
                        "rg_policy": "controlled_fallback",
                        "max_slice_age_minutes": 240,
                    }
                },
            )
            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "rg TODO src"},
            }
            result = _run_pretool(root, payload, hooks_mode="fast")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            hook_output = data.get("hookSpecificOutput", {})
            self.assertEqual(hook_output.get("permissionDecision"), "ask")
            self.assertIn("rg_without_slice", str(hook_output.get("permissionDecisionReason") or ""))

    def test_allows_rg_with_fresh_manifest_and_records_metrics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rg-guard-allow-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "RG-GUARD-3"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_key)
            _write_maps(root, ticket, scope_key, work_item_key)
            write_json(
                root,
                "config/gates.json",
                {
                    "memory": {
                        "slice_enforcement": "warn",
                        "enforce_stages": ["implement"],
                        "rg_policy": "controlled_fallback",
                        "max_slice_age_minutes": 240,
                    }
                },
            )
            write_json(
                root,
                f"reports/context/{ticket}-memory-slices.implement.{scope_key}.pack.json",
                {
                    "schema": "aidd.memory.slices.manifest.v1",
                    "schema_version": "aidd.memory.slices.manifest.v1",
                    "ticket": ticket,
                    "stage": "implement",
                    "scope_key": scope_key,
                    "generated_at": "2099-01-01T00:00:00Z",
                    "updated_at": "2099-01-01T00:00:00Z",
                    "slices": {"cols": ["query", "slice_pack", "latest_alias", "hits"], "rows": []},
                },
            )

            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "rg TODO src"},
            }
            result = _run_pretool(root, payload, hooks_mode="strict")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            hook_output = data.get("hookSpecificOutput", {})
            self.assertEqual(hook_output.get("permissionDecision"), "allow")
            self.assertIn("ast_index_fallback_rg", str(hook_output.get("permissionDecisionReason") or ""))

            quality_path = root / "reports" / "observability" / f"{ticket}.context-quality.json"
            self.assertTrue(quality_path.exists())
            metrics = json.loads(quality_path.read_text(encoding="utf-8")).get("metrics") or {}
            self.assertGreaterEqual(int(metrics.get("rg_invocations") or 0), 1)


if __name__ == "__main__":
    unittest.main()

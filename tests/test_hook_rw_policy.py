import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT, ensure_project_root, write_active_state, write_file, write_json

HOOK_SCRIPT = REPO_ROOT / "hooks" / "context_gc_pretooluse.py"


def _run_pretool(
    root: Path,
    payload: dict,
    *,
    hooks_mode: str,
    context_gc_mode: str = "off",
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
    env["AIDD_CONTEXT_GC"] = context_gc_mode
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


def _map_base(root: Path, ticket: str, scope_key: str) -> Path:
    _ = scope_key
    return root / "reports" / "context" / ticket


def _write_maps(root: Path, ticket: str, stage: str, scope_key: str, work_item_key: str) -> None:
    base = _map_base(root, ticket, scope_key)
    write_json(
        root,
        f"reports/context/{ticket}/{scope_key}.readmap.json",
        {
            "schema": "aidd.readmap.v1",
            "ticket": ticket,
            "stage": stage,
            "scope_key": scope_key,
            "work_item_key": work_item_key,
            "generated_at": "2024-01-01T00:00:00Z",
            "entries": [],
            "allowed_paths": ["src/allowed.py"],
            "loop_allowed_paths": [],
        },
    )
    write_json(
        root,
        f"reports/context/{ticket}/{scope_key}.writemap.json",
        {
            "schema": "aidd.writemap.v1",
            "ticket": ticket,
            "stage": stage,
            "scope_key": scope_key,
            "work_item_key": work_item_key,
            "generated_at": "2024-01-01T00:00:00Z",
            "allowed_paths": ["src/allowed.py", "docs/plan/demo.md"],
            "docops_only_paths": [f"aidd/docs/tasklist/{ticket}.md", f"aidd/reports/context/{ticket}.pack.md"],
            "always_allow": ["aidd/reports/**", "aidd/reports/actions/**"],
        },
    )
    write_file(
        root,
        f"reports/loops/{ticket}/{scope_key}.loop.pack.md",
        "\n".join(
            [
                "---",
                "schema: aidd.loop_pack.v1",
                f"ticket: {ticket}",
                f"scope_key: {scope_key}",
                f"work_item_key: {work_item_key}",
                "boundaries:",
                "  allowed_paths:",
                "    - src/from-loop/**",
                "  forbidden_paths: []",
                "---",
                "# Loop Pack",
            ]
        )
        + "\n",
    )
    base.mkdir(parents=True, exist_ok=True)


class HookReadWritePolicyTests(unittest.TestCase):
    def test_strict_denies_read_outside_readmap(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hook-rw-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RW"
            work_item_key = "iteration_id=I1"
            scope_key = "iteration_id_I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_key)
            _write_maps(root, ticket, "implement", scope_key, work_item_key)
            write_file(root, "src/blocked.py", "print('x')\n")

            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Read",
                "tool_input": {"file_path": "src/blocked.py"},
            }
            result = _run_pretool(root, payload, hooks_mode="strict")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
            self.assertEqual(decision, "deny")
            self.assertIn("readmap", data.get("hookSpecificOutput", {}).get("permissionDecisionReason", "").lower())

    def test_fast_warns_on_read_outside_readmap(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hook-rw-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RW"
            work_item_key = "iteration_id=I1"
            scope_key = "iteration_id_I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_key)
            _write_maps(root, ticket, "implement", scope_key, work_item_key)
            write_file(root, "src/blocked.py", "print('x')\n")

            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Read",
                "tool_input": {"file_path": "src/blocked.py"},
            }
            result = _run_pretool(root, payload, hooks_mode="fast")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
            self.assertEqual(decision, "allow")
            self.assertIn("context-expand", data.get("systemMessage", ""))

    def test_strict_missing_readmap_advises_canonical_stage_rerun(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hook-rw-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RW"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_key)
            write_file(root, "src/blocked.py", "print('x')\n")

            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Read",
                "tool_input": {"file_path": "src/blocked.py"},
            }
            result = _run_pretool(root, payload, hooks_mode="strict")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
            self.assertEqual(decision, "deny")
            message = str(data.get("systemMessage", ""))
            self.assertIn("/feature-dev-aidd:implement", message)
            self.assertNotIn("preflight_prepare.py", message)

    def test_strict_missing_writemap_advises_canonical_stage_rerun(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hook-rw-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RW"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, stage="review", work_item=work_item_key)
            write_file(root, "src/blocked.py", "print('x')\n")

            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "src/blocked.py", "content": "print('x')"},
            }
            result = _run_pretool(root, payload, hooks_mode="strict")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
            self.assertEqual(decision, "deny")
            message = str(data.get("systemMessage", ""))
            self.assertIn("/feature-dev-aidd:review", message)
            self.assertNotIn("preflight_prepare.py", message)

    def test_strict_allows_glob_with_allowed_pattern(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hook-rw-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RW"
            work_item_key = "iteration_id=I1"
            scope_key = "iteration_id_I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_key)
            _write_maps(root, ticket, "implement", scope_key, work_item_key)
            write_file(root, "src/from-loop/file.py", "print('ok')\n")

            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Glob",
                "tool_input": {"path": ".", "pattern": "src/from-loop/*.py"},
            }
            result = _run_pretool(root, payload, hooks_mode="strict")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(result.stdout.strip(), "")

    def test_strict_denies_direct_tasklist_edit_in_loop_stage(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hook-rw-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RW"
            work_item_key = "iteration_id=I1"
            scope_key = "iteration_id_I1"
            write_active_state(root, ticket=ticket, stage="review", work_item=work_item_key)
            _write_maps(root, ticket, "review", scope_key, work_item_key)
            write_file(root, f"docs/tasklist/{ticket}.md", "# tasklist\n")

            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Edit",
                "tool_input": {"file_path": f"docs/tasklist/{ticket}.md"},
            }
            result = _run_pretool(root, payload, hooks_mode="strict")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
            self.assertEqual(decision, "deny")
            self.assertIn("DocOps", data.get("systemMessage", ""))

    def test_strict_denies_write_to_docops_only_paths_from_writemap(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hook-rw-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RW"
            work_item_key = "iteration_id=I1"
            scope_key = "iteration_id_I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_key)
            _write_maps(root, ticket, "implement", scope_key, work_item_key)
            write_file(root, "src/docops-only/guarded.py", "print('x')\n")

            writemap_path = root / "reports" / "context" / ticket / f"{scope_key}.writemap.json"
            payload = json.loads(writemap_path.read_text(encoding="utf-8"))
            docops_only = payload.get("docops_only_paths") or []
            docops_only.append("src/docops-only/**")
            payload["docops_only_paths"] = docops_only
            writemap_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            pretool_payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "src/docops-only/guarded.py", "content": "print('x')"},
            }
            result = _run_pretool(root, pretool_payload, hooks_mode="strict")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
            self.assertEqual(decision, "deny")
            self.assertIn("DocOps-only", data.get("systemMessage", ""))

    def test_fast_warns_on_docops_only_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hook-rw-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RW"
            work_item_key = "iteration_id=I1"
            scope_key = "iteration_id_I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_key)
            _write_maps(root, ticket, "implement", scope_key, work_item_key)
            write_file(root, "src/docops-only/guarded.py", "print('x')\n")

            writemap_path = root / "reports" / "context" / ticket / f"{scope_key}.writemap.json"
            payload = json.loads(writemap_path.read_text(encoding="utf-8"))
            docops_only = payload.get("docops_only_paths") or []
            docops_only.append("src/docops-only/**")
            payload["docops_only_paths"] = docops_only
            writemap_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            pretool_payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "src/docops-only/guarded.py", "content": "print('x')"},
            }
            result = _run_pretool(root, pretool_payload, hooks_mode="fast")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
            self.assertEqual(decision, "allow")
            self.assertIn("DocOps-only", data.get("systemMessage", ""))

    def test_strict_denies_direct_loop_stage_result_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hook-rw-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RW"
            work_item_key = "iteration_id=I1"
            scope_key = "iteration_id_I1"
            write_active_state(root, ticket=ticket, stage="review", work_item=work_item_key)
            _write_maps(root, ticket, "review", scope_key, work_item_key)
            write_file(
                root,
                f"reports/loops/{ticket}/{scope_key}/stage.review.result.json",
                "{}\n",
            )

            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {
                    "file_path": f"reports/loops/{ticket}/{scope_key}/stage.review.result.json",
                    "content": "{}",
                },
            }
            result = _run_pretool(root, payload, hooks_mode="strict")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
            self.assertEqual(decision, "deny")
            self.assertIn("stage.*.result.json", data.get("systemMessage", ""))

    def test_fast_warns_on_direct_loop_stage_result_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hook-rw-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RW"
            work_item_key = "iteration_id=I1"
            scope_key = "iteration_id_I1"
            write_active_state(root, ticket=ticket, stage="review", work_item=work_item_key)
            _write_maps(root, ticket, "review", scope_key, work_item_key)
            write_file(
                root,
                f"reports/loops/{ticket}/{scope_key}/stage.review.result.json",
                "{}\n",
            )

            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": f"reports/loops/{ticket}/{scope_key}/stage.review.result.json",
                },
            }
            result = _run_pretool(root, payload, hooks_mode="fast")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
            self.assertEqual(decision, "allow")
            self.assertIn("stage.*.result.json", data.get("systemMessage", ""))

    def test_strict_denies_manual_preflight_prepare_bash_command(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hook-rw-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RW"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")

            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {
                    "command": (
                        "python3 /plugin/skills/aidd-loop/runtime/preflight_prepare.py "
                        f"--ticket {ticket} --stage implement"
                    )
                },
            }
            result = _run_pretool(root, payload, hooks_mode="strict", context_gc_mode="full")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
            self.assertEqual(decision, "deny")
            self.assertIn("manual", data.get("hookSpecificOutput", {}).get("permissionDecisionReason", "").lower())
            self.assertIn("/feature-dev-aidd:implement", data.get("systemMessage", ""))

    def test_fast_warns_on_manual_preflight_prepare_bash_command(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hook-rw-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RW"
            write_active_state(root, ticket=ticket, stage="qa", work_item="iteration_id=I1")

            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {
                    "command": (
                        "python3 /plugin/skills/aidd-loop/runtime/preflight_prepare.py "
                        f"--ticket {ticket} --stage qa"
                    )
                },
            }
            result = _run_pretool(root, payload, hooks_mode="fast", context_gc_mode="full")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
            self.assertEqual(decision, "allow")
            self.assertIn("forbidden", data.get("systemMessage", "").lower())
            self.assertIn("/feature-dev-aidd:qa", data.get("systemMessage", ""))

    def test_strict_denies_manual_preflight_prepare_bash_command_in_light_mode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hook-rw-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RW"
            write_active_state(root, ticket=ticket, stage="review", work_item="iteration_id=I1")

            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {
                    "command": (
                        "python3 /plugin/skills/aidd-loop/runtime/preflight_prepare.py "
                        f"--ticket {ticket} --stage review"
                    )
                },
            }
            result = _run_pretool(root, payload, hooks_mode="strict", context_gc_mode="light")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
            self.assertEqual(decision, "deny")
            self.assertIn("forbidden", data.get("systemMessage", "").lower())
            self.assertIn("/feature-dev-aidd:review", data.get("systemMessage", ""))

    def test_fast_warns_on_manual_preflight_prepare_bash_command_in_off_mode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hook-rw-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RW"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")

            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {
                    "command": (
                        "python3 /plugin/skills/aidd-loop/runtime/preflight_prepare.py "
                        f"--ticket {ticket} --stage implement"
                    )
                },
            }
            result = _run_pretool(root, payload, hooks_mode="fast", context_gc_mode="off")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
            self.assertEqual(decision, "allow")
            self.assertIn("forbidden", data.get("systemMessage", "").lower())
            self.assertIn("/feature-dev-aidd:implement", data.get("systemMessage", ""))

    def test_strict_planning_stage_denies_write_outside_writemap(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hook-rw-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PLAN"
            work_item_key = ""
            scope_key = "DEMO-PLAN"
            write_active_state(root, ticket=ticket, stage="plan", work_item=work_item_key)
            _write_maps(root, ticket, "plan", scope_key, work_item_key)

            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "docs/plan/other.md", "content": "x"},
            }
            result = _run_pretool(root, payload, hooks_mode="strict")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
            self.assertEqual(decision, "deny")
            self.assertIn("planning-stage", data.get("hookSpecificOutput", {}).get("permissionDecisionReason", ""))

    def test_reports_actions_write_is_always_allowed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hook-rw-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RW"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_key)
            write_file(root, "reports/actions/DEMO-RW/iteration_id_I1/tmp.json", "{}\n")

            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "reports/actions/DEMO-RW/iteration_id_I1/tmp.json", "content": "{}"},
            }
            result = _run_pretool(root, payload, hooks_mode="strict")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(result.stdout.strip(), "")

    def test_strict_allows_write_from_loop_pack_boundaries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hook-rw-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-RW"
            work_item_key = "iteration_id=I1"
            scope_key = "iteration_id_I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_key)
            _write_maps(root, ticket, "implement", scope_key, work_item_key)
            write_file(root, "src/from-loop/file.py", "print('ok')\n")

            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "src/from-loop/file.py", "content": "print('ok')"},
            }
            result = _run_pretool(root, payload, hooks_mode="strict")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(result.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()

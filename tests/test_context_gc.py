from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import PAYLOAD_ROOT, git_config_user, git_init, write_active_feature, write_file, write_json

sys.dont_write_bytecode = True

SCRIPTS_ROOT = PAYLOAD_ROOT / "scripts" / "context_gc"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import working_set_builder  # type: ignore  # noqa: E402


USERPROMPT_SCRIPT = SCRIPTS_ROOT / "userprompt_guard.py"
PRETOOLUSE_SCRIPT = SCRIPTS_ROOT / "pretooluse_guard.py"
PRECOMPACT_SCRIPT = SCRIPTS_ROOT / "precompact_snapshot.py"
SESSIONSTART_SCRIPT = SCRIPTS_ROOT / "sessionstart_inject.py"


def _env_for_workspace(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(root)
    env["CLAUDE_PLUGIN_ROOT"] = str(root / "aidd")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _run_hook_script(script: Path, payload: dict, env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=cwd,
        env=env,
    )


class WorkingSetBuilderTests(unittest.TestCase):
    def test_working_set_builder_includes_ticket_and_tasks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_active_feature(root, "demo-ticket", "demo-slug")
            write_file(
                root,
                "docs/prd/demo-ticket.prd.md",
                "# Demo PRD\n\nStatus: draft\n\nLine 1\nLine 2\n",
            )
            write_file(
                root,
                "docs/tasklist/demo-ticket.md",
                "- [ ] Task A\n- [ ] Task B\n- [ ] Task C\n",
            )
            write_json(
                root,
                "config/context_gc.json",
                {
                    "working_set": {
                        "max_tasks": 2,
                        "max_chars": 4000,
                        "include_git_status": False,
                    }
                },
            )

            ws = working_set_builder.build_working_set(root)

            self.assertEqual(ws.ticket, "demo-ticket")
            self.assertEqual(ws.slug, "demo-slug")
            self.assertIn("Ticket: demo-ticket", ws.text)
            self.assertIn("#### Tasklist", ws.text)
            self.assertIn("- [ ] Task A", ws.text)
            self.assertIn("- [ ] Task B", ws.text)
            self.assertNotIn("- [ ] Task C", ws.text)

    def test_working_set_builder_truncates_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_active_feature(root, "demo-ticket")
            write_file(
                root,
                "docs/prd/demo-ticket.prd.md",
                "# Demo PRD\n\nStatus: draft\n\n" + ("Long line\n" * 200),
            )
            write_json(
                root,
                "config/context_gc.json",
                {"working_set": {"max_chars": 200, "include_git_status": False}},
            )

            ws = working_set_builder.build_working_set(root)

            self.assertLessEqual(len(ws.text), 200)
            self.assertIn("... (truncated)", ws.text)

    def test_working_set_builder_includes_git_status(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git not available")
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            git_init(root)
            git_config_user(root)
            write_active_feature(root, "demo-ticket")
            (root / "README.md").write_text("hello\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)
            (root / "README.md").write_text("hello again\n", encoding="utf-8")
            write_json(
                root,
                "config/context_gc.json",
                {"working_set": {"include_git_status": True}},
            )

            ws = working_set_builder.build_working_set(root)

            self.assertIn("#### Repo state", ws.text)
            self.assertIn("- Branch:", ws.text)
            self.assertIn("- Dirty files: 1", ws.text)


class UserPromptGuardTests(unittest.TestCase):
    def test_userprompt_guard_soft_warning(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/.active_ticket", "demo")
            write_json(
                root,
                "config/context_gc.json",
                {
                    "context_limits": {"mode": "bytes"},
                    "transcript_limits": {
                        "soft_bytes": 10,
                        "hard_bytes": 20,
                        "hard_behavior": "block_prompt",
                    },
                },
            )
            transcript = root / "transcript.jsonl"
            transcript.write_text("x" * 15, encoding="utf-8")

            payload = {
                "hook_event_name": "UserPromptSubmit",
                "transcript_path": str(transcript),
            }
            result = _run_hook_script(USERPROMPT_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertIn("Context GC(bytes): transcript is large", data.get("systemMessage", ""))
            self.assertNotIn("decision", data)

    def test_userprompt_guard_hard_block(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/.active_ticket", "demo")
            write_json(
                root,
                "config/context_gc.json",
                {
                    "context_limits": {"mode": "bytes"},
                    "transcript_limits": {
                        "soft_bytes": 10,
                        "hard_bytes": 20,
                        "hard_behavior": "block_prompt",
                    },
                },
            )
            transcript = root / "transcript.jsonl"
            transcript.write_text("x" * 25, encoding="utf-8")

            payload = {
                "hook_event_name": "UserPromptSubmit",
                "transcript_path": str(transcript),
            }
            result = _run_hook_script(USERPROMPT_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data.get("decision"), "block")

    def test_userprompt_guard_token_warns(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/.active_ticket", "demo")
            write_json(
                root,
                "config/context_gc.json",
                {
                    "context_limits": {
                        "mode": "tokens",
                        "max_context_tokens": 100,
                        "autocompact_buffer_tokens": 0,
                        "reserve_next_turn_tokens": 0,
                        "warn_pct_of_usable": 80,
                        "block_pct_of_usable": 95,
                    }
                },
            )
            transcript = root / "transcript.jsonl"
            transcript.write_text(
                json.dumps(
                    {
                        "message": {
                            "usage": {
                                "input_tokens": 85,
                                "cache_read_input_tokens": 0,
                                "cache_creation_input_tokens": 0,
                            }
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = {
                "hook_event_name": "UserPromptSubmit",
                "transcript_path": str(transcript),
            }
            result = _run_hook_script(USERPROMPT_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertIn("Context GC: high context usage", data.get("systemMessage", ""))

    def test_userprompt_guard_token_blocks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/.active_ticket", "demo")
            write_json(
                root,
                "config/context_gc.json",
                {
                    "context_limits": {
                        "mode": "tokens",
                        "max_context_tokens": 100,
                        "autocompact_buffer_tokens": 0,
                        "reserve_next_turn_tokens": 0,
                        "warn_pct_of_usable": 80,
                        "block_pct_of_usable": 90,
                    }
                },
            )
            transcript = root / "transcript.jsonl"
            transcript.write_text(
                json.dumps(
                    {
                        "message": {
                            "usage": {
                                "input_tokens": 95,
                                "cache_read_input_tokens": 0,
                                "cache_creation_input_tokens": 0,
                            }
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = {
                "hook_event_name": "UserPromptSubmit",
                "transcript_path": str(transcript),
            }
            result = _run_hook_script(USERPROMPT_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data.get("decision"), "block")

    def test_userprompt_guard_token_fallbacks_to_bytes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/.active_ticket", "demo")
            write_json(
                root,
                "config/context_gc.json",
                {
                    "context_limits": {"mode": "tokens", "max_context_tokens": 100},
                    "transcript_limits": {"soft_bytes": 5, "hard_bytes": 10, "hard_behavior": "warn_only"},
                },
            )
            transcript = root / "transcript.jsonl"
            transcript.write_text("x" * 8, encoding="utf-8")

            payload = {
                "hook_event_name": "UserPromptSubmit",
                "transcript_path": str(transcript),
            }
            result = _run_hook_script(USERPROMPT_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertIn("Context GC(bytes): transcript is large", data.get("systemMessage", ""))

    def test_userprompt_guard_ignores_sidechain_and_api_errors(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/.active_ticket", "demo")
            write_json(
                root,
                "config/context_gc.json",
                {
                    "context_limits": {
                        "mode": "tokens",
                        "max_context_tokens": 100,
                        "autocompact_buffer_tokens": 0,
                        "reserve_next_turn_tokens": 0,
                        "warn_pct_of_usable": 80,
                        "block_pct_of_usable": 90,
                    }
                },
            )
            transcript = root / "transcript.jsonl"
            transcript.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "isSidechain": True,
                                "message": {
                                    "usage": {
                                        "input_tokens": 95,
                                        "cache_read_input_tokens": 0,
                                        "cache_creation_input_tokens": 0,
                                    }
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "isApiErrorMessage": True,
                                "message": {
                                    "usage": {
                                        "input_tokens": 95,
                                        "cache_read_input_tokens": 0,
                                        "cache_creation_input_tokens": 0,
                                    }
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "message": {
                                    "usage": {
                                        "input_tokens": 85,
                                        "cache_read_input_tokens": 0,
                                        "cache_creation_input_tokens": 0,
                                    }
                                }
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            payload = {
                "hook_event_name": "UserPromptSubmit",
                "transcript_path": str(transcript),
            }
            result = _run_hook_script(USERPROMPT_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertIn("Context GC: high context usage", data.get("systemMessage", ""))

    def test_userprompt_guard_respects_reserve_and_buffer(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/.active_ticket", "demo")
            write_json(
                root,
                "config/context_gc.json",
                {
                    "context_limits": {
                        "mode": "tokens",
                        "max_context_tokens": 100,
                        "autocompact_buffer_tokens": 20,
                        "reserve_next_turn_tokens": 10,
                        "warn_pct_of_usable": 80,
                        "block_pct_of_usable": 95,
                    }
                },
            )
            transcript = root / "transcript.jsonl"
            transcript.write_text(
                json.dumps(
                    {
                        "message": {
                            "usage": {
                                "input_tokens": 65,
                                "cache_read_input_tokens": 0,
                                "cache_creation_input_tokens": 0,
                            }
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = {
                "hook_event_name": "UserPromptSubmit",
                "transcript_path": str(transcript),
            }
            result = _run_hook_script(USERPROMPT_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertIn("Context GC: high context usage", data.get("systemMessage", ""))

    def test_userprompt_guard_bytes_warn_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/.active_ticket", "demo")
            write_json(
                root,
                "config/context_gc.json",
                {
                    "context_limits": {"mode": "bytes"},
                    "transcript_limits": {
                        "soft_bytes": 10,
                        "hard_bytes": 20,
                        "hard_behavior": "warn_only",
                    },
                },
            )
            transcript = root / "transcript.jsonl"
            transcript.write_text("x" * 25, encoding="utf-8")

            payload = {
                "hook_event_name": "UserPromptSubmit",
                "transcript_path": str(transcript),
            }
            result = _run_hook_script(USERPROMPT_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertIn("Context GC(bytes): transcript exceeded hard limit", data.get("systemMessage", ""))


class SessionStartInjectTests(unittest.TestCase):
    def test_sessionstart_inject_adds_working_set(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_active_feature(root, "demo-ticket")
            write_file(
                root,
                "docs/prd/demo-ticket.prd.md",
                "# Demo PRD\n\nStatus: draft\n\n",
            )
            write_json(
                root,
                "config/context_gc.json",
                {"working_set": {"include_git_status": False}},
            )
            payload = {"hook_event_name": "SessionStart"}
            result = _run_hook_script(SESSIONSTART_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            hook_output = data.get("hookSpecificOutput", {})
            self.assertEqual(hook_output.get("hookEventName"), "SessionStart")
            context = hook_output.get("additionalContext", "")
            self.assertIn("AIDD Working Set", context)
            self.assertIn("Ticket: demo-ticket", context)


class PreToolUseGuardTests(unittest.TestCase):
    def test_pretooluse_guard_wraps_bash_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/.active_ticket", "demo")
            write_json(
                root,
                "config/context_gc.json",
                {
                    "bash_output_guard": {
                        "enabled": True,
                        "tail_lines": 50,
                        "log_dir": "aidd/reports/logs",
                        "only_for_regex": "docker\\s+logs",
                        "skip_if_regex": "--tail",
                    }
                },
            )
            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "docker logs app"},
            }
            result = _run_hook_script(PRETOOLUSE_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            hook_output = data.get("hookSpecificOutput", {})
            self.assertEqual(hook_output.get("permissionDecision"), "allow")
            updated = hook_output.get("updatedInput", {}).get("command", "")
            self.assertIn("tail -n 50", updated)

    def test_pretooluse_guard_large_read_asks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_json(
                root,
                "config/context_gc.json",
                {"read_guard": {"enabled": True, "max_bytes": 10, "ask_instead_of_deny": True}},
            )
            write_file(root, "docs/large.txt", "x" * 20)
            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Read",
                "tool_input": {"file_path": "aidd/docs/large.txt"},
            }
            result = _run_hook_script(PRETOOLUSE_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            hook_output = data.get("hookSpecificOutput", {})
            self.assertEqual(hook_output.get("permissionDecision"), "ask")

    def test_pretooluse_guard_large_read_denies(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_json(
                root,
                "config/context_gc.json",
                {"read_guard": {"enabled": True, "max_bytes": 10, "ask_instead_of_deny": False}},
            )
            write_file(root, "docs/large.txt", "x" * 20)
            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Read",
                "tool_input": {"file_path": "aidd/docs/large.txt"},
            }
            result = _run_hook_script(PRETOOLUSE_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            hook_output = data.get("hookSpecificOutput", {})
            self.assertEqual(hook_output.get("permissionDecision"), "deny")

    def test_pretooluse_guard_dangerous_bash_asks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/.active_ticket", "demo")
            write_json(
                root,
                "config/context_gc.json",
                {
                    "dangerous_bash_guard": {
                        "enabled": True,
                        "mode": "ask",
                        "patterns": ["rm\\s+-rf"],
                    }
                },
            )
            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "rm -rf /tmp/demo"},
            }
            result = _run_hook_script(PRETOOLUSE_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            hook_output = data.get("hookSpecificOutput", {})
            self.assertEqual(hook_output.get("permissionDecision"), "ask")

    def test_pretooluse_guard_dangerous_bash_denies(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/.active_ticket", "demo")
            write_json(
                root,
                "config/context_gc.json",
                {
                    "dangerous_bash_guard": {
                        "enabled": True,
                        "mode": "deny",
                        "patterns": ["git\\s+reset\\s+--hard"],
                    }
                },
            )
            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "git reset --hard HEAD~1"},
            }
            result = _run_hook_script(PRETOOLUSE_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            hook_output = data.get("hookSpecificOutput", {})
            self.assertEqual(hook_output.get("permissionDecision"), "deny")

    def test_pretooluse_guard_dangerous_bash_runs_when_output_guard_disabled(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/.active_ticket", "demo")
            write_json(
                root,
                "config/context_gc.json",
                {
                    "bash_output_guard": {"enabled": False},
                    "dangerous_bash_guard": {
                        "enabled": True,
                        "mode": "deny",
                        "patterns": ["rm\\s+-rf"],
                    },
                },
            )
            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "rm -rf /tmp/demo"},
            }
            result = _run_hook_script(PRETOOLUSE_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            hook_output = data.get("hookSpecificOutput", {})
            self.assertEqual(hook_output.get("permissionDecision"), "deny")

    def test_pretooluse_guard_resolves_log_dir_in_aidd(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_file(root, "docs/.active_ticket", "demo")
            write_json(
                root,
                "config/context_gc.json",
                {
                    "bash_output_guard": {
                        "enabled": True,
                        "tail_lines": 10,
                        "log_dir": "reports/logs",
                        "only_for_regex": "docker\\s+logs",
                        "skip_if_regex": "--tail",
                    }
                },
            )
            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "docker logs app"},
            }
            result = _run_hook_script(PRETOOLUSE_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            hook_output = data.get("hookSpecificOutput", {})
            updated = hook_output.get("updatedInput", {}).get("command", "")
            expected = (root / "aidd" / "reports" / "logs").resolve()
            self.assertIn(str(expected), updated)

    def test_pretooluse_guard_resolves_read_path_without_aidd_prefix(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_json(
                root,
                "config/context_gc.json",
                {"read_guard": {"enabled": True, "max_bytes": 10, "ask_instead_of_deny": True}},
            )
            write_file(root, "docs/large.txt", "x" * 20)
            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Read",
                "tool_input": {"file_path": "docs/large.txt"},
            }
            result = _run_hook_script(PRETOOLUSE_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            hook_output = data.get("hookSpecificOutput", {})
            self.assertEqual(hook_output.get("permissionDecision"), "ask")


class PreCompactSnapshotTests(unittest.TestCase):
    def test_precompact_snapshot_writes_by_ticket_index(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-gc-") as tmpdir:
            root = Path(tmpdir)
            write_active_feature(root, "demo-ticket")
            write_json(root, "config/context_gc.json", {"enabled": True})
            transcript = root / "transcript.jsonl"
            transcript.write_text("line1\n", encoding="utf-8")

            payload = {
                "hook_event_name": "PreCompact",
                "session_id": "session-1",
                "transcript_path": str(transcript),
            }
            result = _run_hook_script(PRECOMPACT_SCRIPT, payload, _env_for_workspace(root), root)

            self.assertEqual(result.returncode, 0, result.stderr)
            session_path = root / "aidd" / "reports" / "context" / "session-1" / "working_set.md"
            ticket_path = (
                root
                / "aidd"
                / "reports"
                / "context"
                / "by-ticket"
                / "demo-ticket"
                / "session-1"
                / "working_set.md"
            )
            latest_ticket = (
                root
                / "aidd"
                / "reports"
                / "context"
                / "by-ticket"
                / "demo-ticket"
                / "latest_working_set.md"
            )
            self.assertTrue(session_path.exists())
            self.assertTrue(ticket_path.exists())
            self.assertTrue(latest_ticket.exists())


if __name__ == "__main__":
    unittest.main()

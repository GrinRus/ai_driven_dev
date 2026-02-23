import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT, cli_cmd, cli_env, ensure_project_root, write_active_state, write_json, write_tasklist_ready


class ContextExpandTests(unittest.TestCase):
    def _prepare_preflight(
        self,
        root: Path,
        ticket: str,
        scope_key: str,
        work_item_key: str,
        *,
        stage: str = "implement",
    ) -> None:
        context_base = f"reports/context/{ticket}"
        loops_base = f"reports/loops/{ticket}/{scope_key}"
        result = subprocess.run(
            cli_cmd(
                "preflight-prepare",
                "--ticket",
                ticket,
                "--scope-key",
                scope_key,
                "--work-item-key",
                work_item_key,
                "--stage",
                stage,
                "--actions-template",
                f"reports/actions/{ticket}/{scope_key}/{stage}.actions.template.json",
                "--readmap-json",
                f"{context_base}/{scope_key}.readmap.json",
                "--readmap-md",
                f"{context_base}/{scope_key}.readmap.md",
                "--writemap-json",
                f"{context_base}/{scope_key}.writemap.json",
                "--writemap-md",
                f"{context_base}/{scope_key}.writemap.md",
                "--result",
                f"{loops_base}/stage.preflight.result.json",
            ),
            cwd=root,
            env=cli_env(),
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            raise AssertionError(f"preflight failed: {result.stderr}\n{result.stdout}")

    def test_context_expand_updates_maps_and_audit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-expand-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-CTX"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, stage="implement", work_item=work_item_key)
            write_tasklist_ready(root, ticket)
            self._prepare_preflight(root, ticket, scope_key, work_item_key)

            result = subprocess.run(
                cli_cmd(
                    "context-expand",
                    "--ticket",
                    ticket,
                    "--scope-key",
                    scope_key,
                    "--work-item-key",
                    work_item_key,
                    "--stage",
                    "implement",
                    "--path",
                    "src/new_feature.py",
                    "--reason-code",
                    "missing_context",
                    "--reason",
                    "Need service context",
                    "--expand-write",
                ),
                cwd=root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            context_base = root / "reports" / "context" / ticket
            readmap = json.loads((context_base / f"{scope_key}.readmap.json").read_text(encoding="utf-8"))
            writemap = json.loads((context_base / f"{scope_key}.writemap.json").read_text(encoding="utf-8"))

            self.assertIn("src/new_feature.py", readmap.get("allowed_paths", []))
            self.assertIn("src/new_feature.py", writemap.get("allowed_paths", []))

            audit_path = root / "reports" / "actions" / ticket / scope_key / "context-expand.audit.jsonl"
            self.assertTrue(audit_path.exists(), "context-expand audit trail is required")
            entries = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertTrue(entries, "audit trail must contain at least one entry")
            latest = entries[-1]
            self.assertEqual(latest.get("schema"), "aidd.context_expand.audit.v1")
            self.assertEqual(latest.get("path"), "src/new_feature.py")
            self.assertEqual(latest.get("reason_code"), "missing_context")
            self.assertTrue(latest.get("expand_write"))

            writemap_md = (context_base / f"{scope_key}.writemap.md").read_text(encoding="utf-8")
            self.assertIn("## Loop Allowed Paths", writemap_md)
            self.assertIn(f"docs/tasklist/{ticket}.md", writemap_md)

    def test_context_expand_runtime_uses_active_stage_by_default(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-expand-wrapper-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-CTX-WRAPPER"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, stage="review", work_item=work_item_key)
            write_tasklist_ready(root, ticket)
            self._prepare_preflight(root, ticket, scope_key, work_item_key, stage="review")

            result = subprocess.run(
                cli_cmd(
                    "context-expand",
                    "--ticket",
                    ticket,
                    "--scope-key",
                    scope_key,
                    "--work-item-key",
                    work_item_key,
                    "--path",
                    "src/wrapper-default-stage.py",
                    "--reason-code",
                    "wrapper_default_stage",
                    "--reason",
                    "Ensure wrapper uses active stage",
                    "--no-regenerate-pack",
                ),
                cwd=root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            audit_path = root / "reports" / "actions" / ticket / scope_key / "context-expand.audit.jsonl"
            self.assertTrue(audit_path.exists())
            entries = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertTrue(entries)
            self.assertEqual(entries[-1].get("stage"), "review")

    def test_context_expand_blocks_when_loop_pack_regeneration_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-expand-fail-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-CTX-FAIL"
            work_item_key = "iteration_id=I404"
            scope_key = "iteration_id_I404"
            write_active_state(root, ticket=ticket, stage="review", work_item=work_item_key)
            write_tasklist_ready(root, ticket)

            context_base = f"reports/context/{ticket}"
            write_json(
                root,
                f"{context_base}/{scope_key}.readmap.json",
                {
                    "schema": "aidd.readmap.v1",
                    "ticket": ticket,
                    "stage": "review",
                    "scope_key": scope_key,
                    "work_item_key": work_item_key,
                    "generated_at": "2024-01-01T00:00:00Z",
                    "entries": [],
                    "allowed_paths": ["src/**"],
                    "loop_allowed_paths": [],
                },
            )
            write_json(
                root,
                f"{context_base}/{scope_key}.writemap.json",
                {
                    "schema": "aidd.writemap.v1",
                    "ticket": ticket,
                    "stage": "review",
                    "scope_key": scope_key,
                    "work_item_key": work_item_key,
                    "generated_at": "2024-01-01T00:00:00Z",
                    "allowed_paths": ["src/**"],
                    "loop_allowed_paths": [],
                    "docops_only_paths": [],
                    "always_allow": ["aidd/reports/**", "aidd/reports/actions/**"],
                },
            )

            result = subprocess.run(
                cli_cmd(
                    "context-expand",
                    "--ticket",
                    ticket,
                    "--scope-key",
                    scope_key,
                    "--work-item-key",
                    work_item_key,
                    "--stage",
                    "review",
                    "--path",
                    "src/missing-loop-item.py",
                    "--reason-code",
                    "missing_loop_item",
                    "--reason",
                    "Work item not present in tasklist",
                ),
                cwd=root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("loop_pack_regeneration_failed", result.stdout)

            audit_path = root / "reports" / "actions" / ticket / scope_key / "context-expand.audit.jsonl"
            self.assertTrue(audit_path.exists())
            entries = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertTrue(entries)
            self.assertFalse(entries[-1].get("loop_pack_regenerated"))


if __name__ == "__main__":
    unittest.main()

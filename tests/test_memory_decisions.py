import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from aidd_runtime import decision_append, memory_pack
from tests.helpers import cli_cmd, cli_env


class MemoryDecisionsTests(unittest.TestCase):
    def test_append_and_pack_decisions(self) -> None:
        with tempfile.TemporaryDirectory(prefix="memory-decisions-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = workspace / "aidd"
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                cli_cmd("init"),
                cwd=workspace,
                env=cli_env(),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            ticket = "MEM-DEC-1"
            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rc1 = decision_append.main(
                    [
                        "--ticket",
                        ticket,
                        "--decision-id",
                        "DEC-1",
                        "--title",
                        "Use canonical routing",
                        "--decision",
                        "Remove set_stage.py fallback",
                        "--rationale",
                        "Avoid non-canonical runtime path",
                        "--tags",
                        "plan,runtime",
                    ]
                )
                self.assertEqual(rc1, 0)

                rc2 = decision_append.main(
                    [
                        "--ticket",
                        ticket,
                        "--decision-id",
                        "DEC-2",
                        "--title",
                        "Supersede fallback policy",
                        "--decision",
                        "Enable strict canonical-only handoff",
                        "--supersedes",
                        "DEC-1",
                    ]
                )
                self.assertEqual(rc2, 0)

                pack_rc = memory_pack.main(["--ticket", ticket, "--top-n", "5"])
                self.assertEqual(pack_rc, 0)
            finally:
                os.chdir(old_cwd)

            decisions_log = project_root / "reports" / "memory" / f"{ticket}.decisions.jsonl"
            pack_path = project_root / "reports" / "memory" / f"{ticket}.decisions.pack.json"
            self.assertTrue(decisions_log.exists())
            self.assertTrue(pack_path.exists())

            rows = [json.loads(line) for line in decisions_log.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0].get("decision_id"), "DEC-1")
            self.assertEqual(rows[1].get("decision_id"), "DEC-2")

            pack_payload = json.loads(pack_path.read_text(encoding="utf-8"))
            active_ids = {item.get("decision_id") for item in (pack_payload.get("active") or [])}
            superseded_ids = {item.get("decision_id") for item in (pack_payload.get("superseded") or [])}
            self.assertIn("DEC-2", active_ids)
            self.assertIn("DEC-1", superseded_ids)

    def test_auto_decision_id_is_stable_and_collision_safe_for_append_chain(self) -> None:
        with tempfile.TemporaryDirectory(prefix="memory-decisions-autoid-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = workspace / "aidd"
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                cli_cmd("init"),
                cwd=workspace,
                env=cli_env(),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            ticket = "MEM-DEC-AUTO-1"
            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rc1 = decision_append.main(
                    [
                        "--ticket",
                        ticket,
                        "--title",
                        "Same title",
                        "--decision",
                        "Same decision",
                        "--rationale",
                        "Same rationale",
                    ]
                )
                self.assertEqual(rc1, 0)
                rc2 = decision_append.main(
                    [
                        "--ticket",
                        ticket,
                        "--title",
                        "Same title",
                        "--decision",
                        "Same decision",
                        "--rationale",
                        "Same rationale",
                    ]
                )
                self.assertEqual(rc2, 0)
            finally:
                os.chdir(old_cwd)

            decisions_log = project_root / "reports" / "memory" / f"{ticket}.decisions.jsonl"
            rows = [json.loads(line) for line in decisions_log.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(rows), 2)
            self.assertNotEqual(rows[0].get("decision_id"), rows[1].get("decision_id"))
            self.assertEqual(rows[1].get("prev_hash"), rows[0].get("entry_hash"))

    def test_actions_apply_supports_memory_decision_append(self) -> None:
        with tempfile.TemporaryDirectory(prefix="memory-actions-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = workspace / "aidd"
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                cli_cmd("init"),
                cwd=workspace,
                env=cli_env(),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            ticket = "MEM-ACT-1"
            actions_path = project_root / "reports" / "actions" / ticket / "iteration_id_I1" / "implement.actions.json"
            actions_path.parent.mkdir(parents=True, exist_ok=True)
            actions_path.write_text(
                json.dumps(
                    {
                        "schema_version": "aidd.actions.v1",
                        "stage": "implement",
                        "ticket": ticket,
                        "scope_key": "iteration_id_I1",
                        "work_item_key": "iteration_id=I1",
                        "allowed_action_types": ["memory_ops.decision_append"],
                        "actions": [
                            {
                                "type": "memory_ops.decision_append",
                                "params": {
                                    "title": "Record memory action decision",
                                    "decision": "Use validated actions path for decision writes",
                                    "rationale": "Keep writes within canonical docops flow",
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with tempfile.TemporaryDirectory(prefix="memory-actions-runner-") as runner_tmp:
                result = subprocess.run(
                    cli_cmd("actions-apply", "--actions", str(actions_path), "--root", str(project_root)),
                    cwd=Path(runner_tmp),
                    env=cli_env(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
            self.assertEqual(result.returncode, 0, msg=f"stdout={result.stdout}\nstderr={result.stderr}")

            decisions_log = project_root / "reports" / "memory" / f"{ticket}.decisions.jsonl"
            decisions_pack = project_root / "reports" / "memory" / f"{ticket}.decisions.pack.json"
            self.assertTrue(decisions_log.exists())
            self.assertTrue(decisions_pack.exists())


if __name__ == "__main__":
    unittest.main()

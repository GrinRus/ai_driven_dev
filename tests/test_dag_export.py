import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_active_state, write_file, write_json


def _loop_pack(ticket: str, scope_key: str, work_item_key: str, allowed_paths: list[str]) -> str:
    allowed_lines = "\n".join(f"    - {item}" for item in allowed_paths)
    return (
        "---\n"
        "schema: aidd.loop_pack.v1\n"
        f"ticket: {ticket}\n"
        f"scope_key: {scope_key}\n"
        f"work_item_key: {work_item_key}\n"
        "boundaries:\n"
        "  allowed_paths:\n"
        f"{allowed_lines}\n"
        "  forbidden_paths: []\n"
        "---\n"
        "# Loop Pack\n"
    )


class DagExportTests(unittest.TestCase):
    def test_dag_export_builds_nodes_and_conflicts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dag-export-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-DAG"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")

            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I1.loop.pack.md",
                _loop_pack(ticket, "iteration_id_I1", "iteration_id=I1", ["src/shared/**", "src/a/**"]),
            )
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I2.loop.pack.md",
                _loop_pack(ticket, "iteration_id_I2", "iteration_id=I2", ["src/shared/**", "src/b/**"]),
            )

            write_json(
                root,
                f"reports/context/{ticket}/iteration_id_I1.writemap.json",
                {
                    "schema": "aidd.writemap.v1",
                    "ticket": ticket,
                    "stage": "implement",
                    "scope_key": "iteration_id_I1",
                    "work_item_key": "iteration_id=I1",
                    "generated_at": "2024-01-01T00:00:00Z",
                    "allowed_paths": ["src/shared/**", "src/a/**"],
                    "docops_only_paths": [],
                    "always_allow": ["aidd/reports/**", "aidd/reports/actions/**"],
                },
            )
            write_json(
                root,
                f"reports/context/{ticket}/iteration_id_I2.writemap.json",
                {
                    "schema": "aidd.writemap.v1",
                    "ticket": ticket,
                    "stage": "implement",
                    "scope_key": "iteration_id_I2",
                    "work_item_key": "iteration_id=I2",
                    "generated_at": "2024-01-01T00:00:00Z",
                    "allowed_paths": ["src/shared/**", "src/b/**"],
                    "docops_only_paths": [],
                    "always_allow": ["aidd/reports/**", "aidd/reports/actions/**"],
                },
            )

            result = subprocess.run(
                cli_cmd("dag-export", "--ticket", ticket),
                cwd=root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            dag_json_path = root / "reports" / "dag" / f"{ticket}.json"
            dag_md_path = root / "reports" / "dag" / f"{ticket}.md"
            self.assertTrue(dag_json_path.exists())
            self.assertTrue(dag_md_path.exists())

            payload = json.loads(dag_json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "aidd.dag.v1")
            self.assertEqual(len(payload.get("nodes") or []), 8)
            self.assertEqual(len(payload.get("edges") or []), 6)

            conflicts = payload.get("conflicts") or []
            self.assertEqual(len(conflicts), 1)
            conflict = conflicts[0]
            self.assertEqual(conflict.get("recommendation"), "do_not_parallelize")
            self.assertIn("src/shared/**", conflict.get("shared_paths") or [])

            node_ids = [node.get("id") for node in payload.get("nodes") or []]
            self.assertEqual(
                node_ids,
                [
                    "iteration_id_I1:preflight",
                    "iteration_id_I1:implement",
                    "iteration_id_I1:review",
                    "iteration_id_I1:qa",
                    "iteration_id_I2:preflight",
                    "iteration_id_I2:implement",
                    "iteration_id_I2:review",
                    "iteration_id_I2:qa",
                ],
            )

    def test_dag_export_output_is_stable_except_timestamp(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dag-export-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-DAG-STABLE"
            write_active_state(root, ticket=ticket, stage="implement", work_item="iteration_id=I1")

            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I1.loop.pack.md",
                _loop_pack(ticket, "iteration_id_I1", "iteration_id=I1", ["src/single/**"]),
            )

            cmd = cli_cmd("dag-export", "--ticket", ticket)
            first = subprocess.run(cmd, cwd=root, env=cli_env(), text=True, capture_output=True)
            self.assertEqual(first.returncode, 0, msg=first.stderr)
            data1 = json.loads((root / "reports/dag" / f"{ticket}.json").read_text(encoding="utf-8"))

            second = subprocess.run(cmd, cwd=root, env=cli_env(), text=True, capture_output=True)
            self.assertEqual(second.returncode, 0, msg=second.stderr)
            data2 = json.loads((root / "reports/dag" / f"{ticket}.json").read_text(encoding="utf-8"))

            data1.pop("generated_at", None)
            data2.pop("generated_at", None)
            self.assertEqual(data1, data2)


if __name__ == "__main__":
    unittest.main()

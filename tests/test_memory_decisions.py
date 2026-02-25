import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ensure_project_root, write_active_state

from aidd_runtime import decision_append, memory_pack


class MemoryDecisionsTests(unittest.TestCase):
    def test_decision_append_and_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="memory-decisions-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "MEM-DEC-1"
            write_active_state(
                project_root,
                ticket=ticket,
                slug_hint=ticket.lower(),
                stage="implement",
                work_item="iteration_id=I1",
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rc_first = decision_append.main(
                    [
                        "--ticket",
                        ticket,
                        "--topic",
                        "storage",
                        "--decision",
                        "use sqlite",
                        "--alternatives",
                        "postgres",
                        "--rationale",
                        "local workflow",
                    ]
                )
                self.assertEqual(rc_first, 0)

                log_path = project_root / "reports" / "memory" / f"{ticket}.decisions.jsonl"
                lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                self.assertEqual(len(lines), 1)
                first_id = str(lines[0]["decision_id"])

                rc_second = decision_append.main(
                    [
                        "--ticket",
                        ticket,
                        "--topic",
                        "storage",
                        "--decision",
                        "use postgres",
                        "--status",
                        "superseded",
                        "--supersedes",
                        first_id,
                    ]
                )
                self.assertEqual(rc_second, 0)

                # Corrupt one line to ensure pack tracks invalid entries deterministically.
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write("{broken json}\n")

                rc_pack = memory_pack.main(["--ticket", ticket])
                self.assertEqual(rc_pack, 0)
            finally:
                os.chdir(old_cwd)

            pack_path = project_root / "reports" / "memory" / f"{ticket}.decisions.pack.json"
            self.assertTrue(pack_path.exists())
            payload = json.loads(pack_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema_version"), "aidd.memory.decisions.pack.v1")
            self.assertEqual(payload.get("ticket"), ticket)
            self.assertEqual(len(payload.get("active_decisions", {}).get("rows", [])), 1)
            self.assertEqual(len(payload.get("superseded_heads", {}).get("rows", [])), 1)
            self.assertGreaterEqual(int(payload.get("stats", {}).get("invalid_entries", 0)), 1)


if __name__ == "__main__":
    unittest.main()


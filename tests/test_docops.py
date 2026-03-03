import tempfile
import unittest
from pathlib import Path

from aidd_runtime import docops
from tests.helpers import ensure_project_root, write_file, write_tasklist_ready


class DocOpsSetDoneNormalizationTests(unittest.TestCase):
    def test_tasklist_set_iteration_done_accepts_iteration_id_alias(self) -> None:
        with tempfile.TemporaryDirectory(prefix="docops-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-DOCOPS-I"
            write_tasklist_ready(root, ticket=ticket)

            result = docops.tasklist_set_iteration_done(
                root,
                ticket,
                "iteration_id=I2",
                kind="iteration",
            )

            self.assertTrue(result.changed)
            self.assertFalse(result.error)
            tasklist_path = root / "docs" / "tasklist" / f"{ticket}.md"
            tasklist_text = tasklist_path.read_text(encoding="utf-8")
            self.assertIn("- [x] I2: Follow-up (iteration_id: I2)", tasklist_text)

    def test_tasklist_set_handoff_done_accepts_id_alias(self) -> None:
        with tempfile.TemporaryDirectory(prefix="docops-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-DOCOPS-H"
            write_tasklist_ready(root, ticket=ticket)
            tasklist_path = root / "docs" / "tasklist" / f"{ticket}.md"
            tasklist_text = tasklist_path.read_text(encoding="utf-8")
            tasklist_text = tasklist_text.replace(
                "<!-- handoff:manual start -->\n<!-- handoff:manual end -->",
                "- [ ] Review findings sync (id: review:F6)",
            )
            write_file(root, f"docs/tasklist/{ticket}.md", tasklist_text)

            result = docops.tasklist_set_iteration_done(
                root,
                ticket,
                "id=review:F6",
                kind="handoff",
            )

            self.assertTrue(result.changed)
            self.assertFalse(result.error)
            tasklist_text_after = tasklist_path.read_text(encoding="utf-8")
            self.assertIn("- [x] Review findings sync (id: review:F6)", tasklist_text_after)


if __name__ == "__main__":
    unittest.main()

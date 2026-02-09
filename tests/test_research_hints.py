import tempfile
import unittest
from pathlib import Path

from tests.helpers import ensure_project_root

from aidd_runtime import research_hints


class ResearchHintsTests(unittest.TestCase):
    def test_parse_research_hints_splits_and_dedupes(self) -> None:
        text = "\n".join(
            [
                "# PRD",
                "",
                "## AIDD:RESEARCH_HINTS",
                "- **Paths**: `src/app: src/shared,src/app`",
                "- **Keywords**: payment checkout,refund:payment",
                "- **Notes**: verify webhooks; check retries",
            ]
        )

        hints = research_hints.parse_research_hints(text)
        self.assertEqual(hints.paths, ["src/app", "src/shared"])
        self.assertEqual(hints.keywords, ["payment", "checkout", "refund"])
        self.assertEqual(hints.notes, ["verify webhooks", "check retries"])

    def test_parse_research_hints_ignores_template_placeholders(self) -> None:
        text = "\n".join(
            [
                "# PRD",
                "",
                "## AIDD:RESEARCH_HINTS",
                "- **Paths**: `<path1:path2>` (например, `src/app:src/shared`)",
                "- **Keywords**: `<kw1,kw2>` (например, `payment,checkout`)",
                "- **Notes**: `<что искать/проверить>`",
            ]
        )

        hints = research_hints.parse_research_hints(text)
        self.assertEqual(hints.paths, [])
        self.assertEqual(hints.keywords, [])
        self.assertEqual(hints.notes, [])

    def test_load_research_hints_reads_ticket_prd(self) -> None:
        with tempfile.TemporaryDirectory(prefix="research-hints-") as tmpdir:
            workspace = Path(tmpdir)
            root = ensure_project_root(workspace)
            ticket = "HINTS-1"
            prd_path = root / "docs" / "prd" / f"{ticket}.prd.md"
            prd_path.parent.mkdir(parents=True, exist_ok=True)
            prd_path.write_text(
                "\n".join(
                    [
                        "# PRD",
                        "## AIDD:RESEARCH_HINTS",
                        "- Paths: src/main",
                        "- Keywords: checkout",
                        "- Notes: focus gateway integration",
                    ]
                ),
                encoding="utf-8",
            )

            hints = research_hints.load_research_hints(root, ticket)
            self.assertEqual(hints.paths, ["src/main"])
            self.assertEqual(hints.keywords, ["checkout"])
            self.assertEqual(hints.notes, ["focus gateway integration"])

    def test_merge_unique_keeps_order(self) -> None:
        merged = research_hints.merge_unique(["src", "pkg"], ["pkg", "docs"], [])
        self.assertEqual(merged, ["src", "pkg", "docs"])


if __name__ == "__main__":
    unittest.main()

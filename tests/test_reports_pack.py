import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from claude_workflow_cli.tools import reports_pack


def _write_context(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class ReportsPackTests(unittest.TestCase):
    def test_research_context_pack_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            context_path = tmp_path / "reports" / "research" / "demo-context.json"
            payload = {
                "ticket": "DEMO-1",
                "slug": "demo-1",
                "generated_at": "2024-01-01T00:00:00Z",
                "profile": {
                    "is_new_project": False,
                    "src_layers": ["src/main"],
                    "tests_detected": True,
                    "config_detected": True,
                    "logging_artifacts": ["logback.xml"],
                    "recommendations": ["Use baseline"],
                },
            }
            _write_context(context_path, payload)

            pack_path = reports_pack.write_research_context_pack(context_path, root=tmp_path)
            first = pack_path.read_text(encoding="utf-8")
            second = pack_path.read_text(encoding="utf-8")
            self.assertEqual(first, second)

            packed = json.loads(first)
            errors = reports_pack.check_budget(
                first,
                max_chars=reports_pack.RESEARCH_BUDGET["max_chars"],
                max_lines=reports_pack.RESEARCH_BUDGET["max_lines"],
                label="research",
            )
            self.assertFalse(errors)
            self.assertEqual(packed["type"], "research")
            self.assertEqual(packed["kind"], "context")
            self.assertEqual(packed["ticket"], "DEMO-1")

    def test_research_context_pack_truncates_matches(self) -> None:
        matches = [
            {"token": "checkout", "file": f"src/{idx}.kt", "line": idx + 1, "snippet": "x" * 300}
            for idx in range(25)
        ]
        payload = {
            "ticket": "DEMO-4",
            "slug": "demo-4",
            "generated_at": "2024-01-08T00:00:00Z",
            "matches": matches,
        }
        pack = reports_pack.build_research_context_pack(payload, source_path="aidd/reports/research/demo-4-context.json")
        match_rows = pack["matches"]["rows"]
        self.assertEqual(len(match_rows), reports_pack.RESEARCH_LIMITS["matches"])
        self.assertLessEqual(len(match_rows[0][4]), reports_pack.RESEARCH_LIMITS["match_snippet_chars"])

    def test_pack_format_toon_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            context_path = tmp_path / "reports" / "research" / "demo-context.json"
            payload = {"ticket": "DEMO-2", "slug": "demo-2", "generated_at": "2024-01-02T00:00:00Z"}
            _write_context(context_path, payload)

            with patch.dict(os.environ, {"AIDD_PACK_FORMAT": "toon"}, clear=False):
                pack_path = reports_pack.write_research_context_pack(context_path, root=tmp_path)

            self.assertTrue(pack_path.name.endswith(".pack.toon"))
            packed = json.loads(pack_path.read_text(encoding="utf-8"))
            self.assertEqual(packed["ticket"], "DEMO-2")

    def test_qa_pack_includes_id_column(self) -> None:
        payload = {
            "ticket": "QA-1",
            "slug_hint": "qa-1",
            "generated_at": "2024-01-04T00:00:00Z",
            "findings": [
                {
                    "id": "qa-issue-1",
                    "severity": "major",
                    "scope": "tests",
                    "title": "Missing tests",
                    "details": "No tests run",
                    "recommendation": "Add smoke tests",
                }
            ],
        }
        pack = reports_pack.build_qa_pack(payload, source_path="aidd/reports/qa/QA-1.json")
        self.assertEqual(pack["findings"]["cols"][0], "id")
        self.assertIn("blocking", pack["findings"]["cols"])
        self.assertEqual(pack["findings"]["rows"][0][0], "qa-issue-1")

    def test_prd_pack_includes_id_column(self) -> None:
        payload = {
            "ticket": "PRD-1",
            "slug": "prd-1",
            "generated_at": "2024-01-05T00:00:00Z",
            "findings": [
                {
                    "id": "prd-issue-1",
                    "severity": "major",
                    "title": "Placeholder",
                    "details": "TBD present in PRD",
                }
            ],
        }
        pack = reports_pack.build_prd_pack(payload, source_path="aidd/reports/prd/PRD-1.json")
        self.assertEqual(pack["findings"]["cols"][0], "id")
        self.assertEqual(pack["findings"]["rows"][0][0], "prd-issue-1")

    def test_research_pack_budget_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            context_path = tmp_path / "reports" / "research" / "tiny-context.json"
            payload = {"ticket": "DEMO-3", "slug": "demo-3", "generated_at": "2024-01-03T00:00:00Z"}
            _write_context(context_path, payload)

            pack_path = reports_pack.write_research_context_pack(context_path, root=tmp_path)
            pack_text = pack_path.read_text(encoding="utf-8")

            errors = reports_pack.check_budget(
                pack_text,
                max_chars=reports_pack.RESEARCH_BUDGET["max_chars"],
                max_lines=reports_pack.RESEARCH_BUDGET["max_lines"],
                label="research",
            )
            self.assertFalse(errors)

    def test_research_pack_auto_trim_meets_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            context_path = tmp_path / "reports" / "research" / "trim-context.json"
            matches = [
                {"token": "match", "file": f"src/{idx}.py", "line": idx + 1, "snippet": "x" * 400}
                for idx in range(50)
            ]
            payload = {
                "ticket": "TRIM-1",
                "slug": "trim-1",
                "generated_at": "2024-01-07T00:00:00Z",
                "matches": matches,
            }
            _write_context(context_path, payload)

            pack_path = reports_pack.write_research_context_pack(context_path, root=tmp_path)
            pack_text = pack_path.read_text(encoding="utf-8")

            errors = reports_pack.check_budget(
                pack_text,
                max_chars=reports_pack.RESEARCH_BUDGET["max_chars"],
                max_lines=reports_pack.RESEARCH_BUDGET["max_lines"],
                label="research",
            )
            self.assertFalse(errors)

            packed = json.loads(pack_text)
            matches_section = packed.get("matches")
            if matches_section:
                self.assertLess(len(matches_section["rows"]), reports_pack.RESEARCH_LIMITS["matches"])

    def test_budget_helper_explains_how_to_fix(self) -> None:
        text = "x" * 50
        errors = reports_pack.check_budget(text, max_chars=10, max_lines=1, label="demo")
        self.assertTrue(errors)
        self.assertIn("Reduce top-N", errors[0])

    def test_budget_enforcement_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            context_path = tmp_path / "reports" / "research" / "huge-context.json"
            payload = {
                "ticket": "X" * 2000,
                "slug": "huge",
                "generated_at": "2024-01-06T00:00:00Z",
            }
            _write_context(context_path, payload)

            with patch.dict(os.environ, {"AIDD_PACK_ENFORCE_BUDGET": "1"}, clear=False):
                with self.assertRaises(ValueError) as exc:
                    reports_pack.write_research_context_pack(context_path, root=tmp_path)
            self.assertIn("pack budget exceeded", str(exc.exception))

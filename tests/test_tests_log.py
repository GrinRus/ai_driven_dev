import sys
import unittest

from tests.helpers import REPO_ROOT

SRC_ROOT = REPO_ROOT
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from tools.io_utils import append_jsonl
from tools.reports import tests_log


class TestsLogLatestEntryTests(unittest.TestCase):
    def test_latest_entry_returns_none_when_scoped_missing(self):
        import tempfile
        from pathlib import Path

        ticket = "DEMO-1"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            entry, path = tests_log.latest_entry(root, ticket, "I1", stages=["implement"])

            self.assertIsNone(entry)
            self.assertIsNone(path)

    def test_latest_entry_prefers_scoped_log_when_present(self):
        import tempfile
        from pathlib import Path

        ticket = "DEMO-2"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scoped_path = tests_log.tests_log_path(root, ticket, "I1")
            append_jsonl(
                scoped_path,
                {
                    "schema": "aidd.tests_log.v1",
                    "updated_at": "2026-02-02T00:00:00Z",
                    "ticket": ticket,
                    "stage": "implement",
                    "scope_key": "I1",
                    "status": "pass",
                },
            )

            entry, path = tests_log.latest_entry(root, ticket, "I1", stages=["implement"])

            self.assertIsNotNone(entry)
            self.assertEqual(path, scoped_path)


class TestsLogSummaryTests(unittest.TestCase):
    def test_summary_missing_log_returns_skipped(self) -> None:
        import tempfile
        from pathlib import Path

        ticket = "DEMO-MISSING"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            summary, reason_code, path, entry = tests_log.summarize_tests(root, ticket, "I1", stages=["review"])
            self.assertEqual(summary, "skipped")
            self.assertEqual(reason_code, "tests_log_missing")
            self.assertIsNone(entry)
            self.assertIsNone(path)

    def test_summary_pass_maps_to_run(self) -> None:
        import tempfile
        from pathlib import Path

        ticket = "DEMO-PASS"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scoped_path = tests_log.tests_log_path(root, ticket, "I1")
            append_jsonl(
                scoped_path,
                {
                    "schema": "aidd.tests_log.v1",
                    "updated_at": "2026-02-02T00:00:00Z",
                    "ticket": ticket,
                    "stage": "review",
                    "scope_key": "I1",
                    "status": "pass",
                },
            )
            summary, reason_code, path, entry = tests_log.summarize_tests(root, ticket, "I1", stages=["review"])
            self.assertEqual(summary, "run")
            self.assertEqual(reason_code, "")
            self.assertEqual(path, scoped_path)
            self.assertIsNotNone(entry)

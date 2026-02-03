import sys
import unittest

from tests.helpers import REPO_ROOT

SRC_ROOT = REPO_ROOT
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from tools.io_utils import append_jsonl
from tools.reports import tests_log


class TestsLogLatestEntryTests(unittest.TestCase):
    def test_latest_entry_falls_back_to_legacy_when_scoped_missing(self):
        import tempfile
        from pathlib import Path

        ticket = "DEMO-1"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            legacy_path = tests_log.legacy_tests_log_path(root, ticket)
            append_jsonl(
                legacy_path,
                {
                    "schema": "aidd.tests_log.v1",
                    "updated_at": "2026-02-01T00:00:00Z",
                    "ticket": ticket,
                    "stage": "implement",
                    "scope_key": "ticket",
                    "status": "pass",
                },
            )

            entry, path = tests_log.latest_entry(root, ticket, "I1", stages=["implement"])

            self.assertIsNotNone(entry)
            self.assertEqual(path, legacy_path)

    def test_latest_entry_prefers_scoped_log_when_present(self):
        import tempfile
        from pathlib import Path

        ticket = "DEMO-2"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scoped_path = tests_log.tests_log_path(root, ticket, "I1")
            legacy_path = tests_log.legacy_tests_log_path(root, ticket)

            append_jsonl(
                legacy_path,
                {
                    "schema": "aidd.tests_log.v1",
                    "updated_at": "2026-02-01T00:00:00Z",
                    "ticket": ticket,
                    "stage": "implement",
                    "scope_key": "ticket",
                    "status": "pass",
                },
            )
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

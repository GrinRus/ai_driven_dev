import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hooks import hooklib


class HooklibModeTests(unittest.TestCase):
    def test_default_hooks_mode_fast(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(hooklib.resolve_hooks_mode(), "fast")

    def test_strict_hooks_mode(self) -> None:
        with mock.patch.dict(os.environ, {"AIDD_HOOKS_MODE": "strict"}):
            self.assertEqual(hooklib.resolve_hooks_mode(), "strict")

    def test_invalid_hooks_mode_falls_back_fast(self) -> None:
        with mock.patch.dict(os.environ, {"AIDD_HOOKS_MODE": "weird"}):
            self.assertEqual(hooklib.resolve_hooks_mode(), "fast")

    def test_append_event_dedup_warn_emits_single_drop_marker(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hooklib-dedup-") as tmpdir:
            root = Path(tmpdir) / "aidd"
            (root / "docs").mkdir(parents=True, exist_ok=True)
            (root / "docs" / ".active.json").write_text(
                json.dumps({"ticket": "TST-DEDUP", "slug_hint": "tst-dedup"}),
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"AIDD_HOOK_EVENT_DEDUP_WINDOW_SECONDS": "3600"}, clear=False):
                hooklib.append_event(root, "gate-tests", "warn", source="hook gate-tests")
                hooklib.append_event(root, "gate-tests", "warn", source="hook gate-tests")
                hooklib.append_event(root, "gate-tests", "warn", source="hook gate-tests")
            events_path = root / "reports" / "events" / "TST-DEDUP.jsonl"
            lines = events_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            second = json.loads(lines[1])
            self.assertNotIn("details", first)
            self.assertEqual(second.get("details", {}).get("dedup_drop_marker"), 1)
            self.assertEqual(second.get("details", {}).get("dedup_key"), "TST-DEDUP:gate-tests:warn:")

    def test_append_event_does_not_dedup_pass_status(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hooklib-dedup-pass-") as tmpdir:
            root = Path(tmpdir) / "aidd"
            (root / "docs").mkdir(parents=True, exist_ok=True)
            (root / "docs" / ".active.json").write_text(
                json.dumps({"ticket": "TST-DEDUP-PASS", "slug_hint": "tst-dedup-pass"}),
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"AIDD_HOOK_EVENT_DEDUP_WINDOW_SECONDS": "3600"}, clear=False):
                hooklib.append_event(root, "gate-tests", "pass", source="hook gate-tests")
                hooklib.append_event(root, "gate-tests", "pass", source="hook gate-tests")
            events_path = root / "reports" / "events" / "TST-DEDUP-PASS.jsonl"
            lines = events_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)


if __name__ == "__main__":
    unittest.main()

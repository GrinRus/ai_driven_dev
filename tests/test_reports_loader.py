from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aidd_runtime.reports import loader


class ReportsLoaderTests(unittest.TestCase):
    def test_load_report_prefers_pack_and_falls_back_to_json(self) -> None:
        with tempfile.TemporaryDirectory(prefix="reports-loader-") as tmpdir:
            root = Path(tmpdir)
            pack_path = root / "report.pack.json"
            json_path = root / "report.json"
            json_path.write_text(json.dumps({"source": "json"}), encoding="utf-8")

            payload, source, used_path = loader.load_report(json_path, pack_path, prefer_pack=True)

            self.assertEqual(source, "json")
            self.assertEqual(used_path, json_path)
            self.assertEqual(payload["source"], "json")

    def test_load_report_missing_paths_error_mentions_pack_and_json(self) -> None:
        with tempfile.TemporaryDirectory(prefix="reports-loader-") as tmpdir:
            root = Path(tmpdir)
            pack_path = root / "missing.pack.json"
            json_path = root / "missing.json"

            with self.assertRaises(FileNotFoundError) as ctx:
                loader.load_report(json_path, pack_path, prefer_pack=True)

            message = str(ctx.exception)
            self.assertIn("missing pack", message)
            self.assertIn(pack_path.as_posix(), message)
            self.assertIn(json_path.as_posix(), message)


if __name__ == "__main__":
    unittest.main()

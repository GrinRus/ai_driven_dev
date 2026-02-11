import builtins
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aidd_runtime import gate_workflow


class GateWorkflowRuntimeResilienceTests(unittest.TestCase):
    def test_reviewer_notice_handles_runtime_import_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gate-workflow-runtime-") as tmpdir:
            root = Path(tmpdir)
            (root / "config").mkdir(parents=True, exist_ok=True)
            (root / "docs").mkdir(parents=True, exist_ok=True)
            (root / "config" / "gates.json").write_text(
                json.dumps(
                    {
                        "reviewer": {
                            "enabled": True,
                            "tests_marker": "aidd/reports/reviewer/{ticket}/{scope_key}.tests.json",
                            "warn_on_missing": True,
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "docs" / ".active.json").write_text(
                json.dumps({"ticket": "DEMO", "work_item": "iteration_id=I1"}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            real_import = builtins.__import__

            def broken_runtime_import(name, globals=None, locals=None, fromlist=(), level=0):
                if name == "aidd_runtime" and fromlist and "runtime" in fromlist:
                    raise ImportError("simulated runtime import failure")
                return real_import(name, globals, locals, fromlist, level)

            with mock.patch("builtins.__import__", side_effect=broken_runtime_import):
                notice = gate_workflow._reviewer_notice(root, "DEMO", "")

            self.assertIn("reviewer runtime fallback", notice)
            self.assertIn("reviewer маркер не найден", notice)
            self.assertIn("iteration_id_I1.tests.json", notice)


if __name__ == "__main__":
    unittest.main()

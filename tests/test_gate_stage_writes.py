import json
import tempfile
import unittest
from pathlib import Path

from tests.helpers import run_hook, write_active_feature, write_active_stage


class GateStageWritesTests(unittest.TestCase):
    def test_stage_allowlists(self) -> None:
        cases = [
            ("review", "docs/tasklist/demo.md", True),
            ("review", "reports/qa/demo.json", True),
            ("review", "docs/.active_stage", True),
            ("review", "src/main/kotlin/App.kt", False),
            ("review", "docs/spec/demo.spec.yaml", False),
            ("qa", "docs/tasklist/demo.md", True),
            ("qa", "reports/qa/demo.json", True),
            ("qa", "docs/.active_feature", True),
            ("qa", "docs/spec/demo.spec.yaml", False),
            ("qa", "src/main/kotlin/App.kt", False),
            ("spec-interview", "docs/spec/demo.spec.yaml", True),
            ("spec-interview", "reports/spec/demo.json", True),
            ("spec-interview", "docs/.active_ticket", True),
            ("spec-interview", "docs/tasklist/demo.md", False),
            ("spec-interview", "src/main/kotlin/App.kt", False),
            ("tasklist", "docs/tasklist/demo.md", True),
            ("tasklist", "reports/research/demo.json", True),
            ("tasklist", "docs/.active_stage", True),
            ("tasklist", "docs/spec/demo.spec.yaml", False),
            ("tasklist", "src/main/kotlin/App.kt", False),
        ]
        with tempfile.TemporaryDirectory(prefix="stage-writes-") as tmpdir:
            root = Path(tmpdir)
            write_active_feature(root, "demo-ticket")
            for stage, file_path, allowed in cases:
                write_active_stage(root, stage)
                payload = json.dumps({"tool_input": {"file_path": file_path}})
                result = run_hook(root, "gate-stage-writes.sh", payload)
                if allowed:
                    self.assertEqual(result.returncode, 0, result.stderr)
                else:
                    self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()

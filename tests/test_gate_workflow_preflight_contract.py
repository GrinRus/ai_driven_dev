import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import REPO_ROOT
from tools import gate_workflow


class GateWorkflowPreflightContractTests(unittest.TestCase):
    def _prepare_root(self, tmpdir: str) -> tuple[Path, str, str]:
        root = Path(tmpdir) / "aidd"
        ticket = "DEMO-PREFLIGHT"
        scope_key = "iteration_id_I1"
        (root / "docs").mkdir(parents=True, exist_ok=True)
        (root / "docs" / ".active.json").write_text(
            '{"ticket":"DEMO-PREFLIGHT","stage":"review","work_item":"iteration_id=I1"}\n',
            encoding="utf-8",
        )
        (root / "docs" / ".active_mode").write_text("loop\n", encoding="utf-8")
        actions_dir = root / "reports" / "actions" / ticket / scope_key
        actions_dir.mkdir(parents=True, exist_ok=True)
        (actions_dir / "review.actions.template.json").write_text("{}\n", encoding="utf-8")
        (actions_dir / "readmap.json").write_text("{}\n", encoding="utf-8")
        (actions_dir / "writemap.json").write_text("{}\n", encoding="utf-8")
        (actions_dir / "stage.preflight.result.json").write_text("{}\n", encoding="utf-8")
        return root, ticket, scope_key

    def test_legacy_preflight_artifacts_are_blocked_by_default(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gate-preflight-") as tmpdir:
            root, ticket, _ = self._prepare_root(tmpdir)
            env = {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}
            with mock.patch.dict(os.environ, env, clear=False):
                ok, message = gate_workflow._loop_preflight_guard(root, ticket, "review", "fast")
            self.assertFalse(ok)
            self.assertIn("preflight_missing", message)
            self.assertIn("reports/context", message)

    def test_legacy_preflight_artifacts_allowed_with_explicit_env(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gate-preflight-") as tmpdir:
            root, ticket, _ = self._prepare_root(tmpdir)
            env = {
                "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
                "AIDD_ALLOW_LEGACY_PREFLIGHT": "1",
            }
            with mock.patch.dict(os.environ, env, clear=False):
                ok, message = gate_workflow._loop_preflight_guard(root, ticket, "review", "fast")
            self.assertTrue(ok)
            self.assertIn("preflight_legacy_path", message)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from tests.helpers import ensure_project_root, write_active_feature, write_json

from aidd_runtime import rlm_manifest
from aidd_runtime import rlm_config


class RlmManifestTests(unittest.TestCase):
    def test_manifest_includes_file_id_and_rev(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-manifest-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-2"
            write_active_feature(project_root, ticket)

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            file_path = workspace / "src" / "demo.py"
            file_path.write_text("print('ok')\n", encoding="utf-8")

            write_json(
                workspace,
                f"reports/research/{ticket}-rlm-targets.json",
                {
                    "ticket": ticket,
                    "slug": ticket,
                    "generated_at": "2024-01-01T00:00:00Z",
                    "files": ["src/demo.py"],
                },
            )

            targets_path = project_root / "reports" / "research" / f"{ticket}-rlm-targets.json"
            payload = rlm_manifest.build_manifest(project_root, ticket, settings={}, targets_path=targets_path)
            self.assertEqual(payload["ticket"], ticket)
            self.assertEqual(len(payload["files"]), 1)
            entry = payload["files"][0]
            self.assertEqual(entry["path"], "src/demo.py")
            self.assertEqual(entry["file_id"], rlm_config.file_id_for_path(Path("src/demo.py")))
            self.assertTrue(entry["rev_sha"])


if __name__ == "__main__":
    unittest.main()

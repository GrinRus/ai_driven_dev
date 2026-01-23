import tempfile
import unittest
from pathlib import Path

from tests.helpers import ensure_project_root, write_active_feature, write_json

from tools import rlm_targets


class RlmTargetsTests(unittest.TestCase):
    def test_rlm_targets_collects_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-targets-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-1"
            write_active_feature(project_root, ticket)

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "app.py").write_text("class App:\n    pass\n", encoding="utf-8")
            (workspace / "src" / "note.txt").write_text("ignore\n", encoding="utf-8")

            plan = project_root / "docs" / "plan" / f"{ticket}.md"
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text(
                "## AIDD:FILES_TOUCHED\n- src/app.py — demo\n",
                encoding="utf-8",
            )

            write_json(
                workspace,
                f"reports/research/{ticket}-targets.json",
                {
                    "ticket": ticket,
                    "slug": ticket,
                    "generated_at": "2024-01-01T00:00:00Z",
                    "paths": ["src"],
                    "paths_discovered": [],
                    "keywords": ["App"],
                },
            )

            payload = rlm_targets.build_targets(project_root, ticket, settings={})
            files = payload.get("files") or []
            self.assertIn("src/app.py", files)
            self.assertNotIn("src/note.txt", files)
            self.assertEqual(payload.get("paths_base"), "workspace")

    def test_rlm_targets_auto_discovers_common_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-targets-auto-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-2"
            write_active_feature(project_root, ticket)

            (workspace / "backend" / "src" / "main" / "java").mkdir(parents=True, exist_ok=True)
            (workspace / "frontend" / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "backend" / "src" / "main" / "java" / "App.java").write_text(
                "class App {}\n",
                encoding="utf-8",
            )
            (workspace / "frontend" / "src" / "App.tsx").write_text(
                "export const App = () => null;\n",
                encoding="utf-8",
            )

            write_json(
                workspace,
                f"reports/research/{ticket}-targets.json",
                {
                    "ticket": ticket,
                    "slug": ticket,
                    "generated_at": "2024-01-01T00:00:00Z",
                    "paths": [],
                    "paths_discovered": [],
                    "keywords": [],
                },
            )

            payload = rlm_targets.build_targets(project_root, ticket, settings={})
            discovered = payload.get("paths_discovered") or []
            self.assertIn("backend/src/main", discovered)
            self.assertIn("frontend/src", discovered)
            files = payload.get("files") or []
            self.assertIn("backend/src/main/java/App.java", files)


if __name__ == "__main__":
    unittest.main()

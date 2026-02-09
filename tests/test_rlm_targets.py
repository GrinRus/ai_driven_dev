import tempfile
import unittest
from pathlib import Path

from tests.helpers import ensure_project_root, write_active_feature

from aidd_runtime import rlm_targets


def _write_prd_hints(
    project_root: Path,
    ticket: str,
    *,
    paths: list[str] | None = None,
    keywords: list[str] | None = None,
    notes: str = "",
) -> None:
    prd_path = project_root / "docs" / "prd" / f"{ticket}.prd.md"
    prd_path.parent.mkdir(parents=True, exist_ok=True)
    path_value = ":".join(paths or [])
    keyword_value = ",".join(keywords or [])
    prd_path.write_text(
        "\n".join(
            [
                "# PRD",
                "",
                "## AIDD:RESEARCH_HINTS",
                f"- Paths: {path_value}",
                f"- Keywords: {keyword_value}",
                f"- Notes: {notes}",
            ]
        ),
        encoding="utf-8",
    )


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
            _write_prd_hints(project_root, ticket, paths=["src"], keywords=["App"])

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
            _write_prd_hints(project_root, ticket, keywords=["app"])

            payload = rlm_targets.build_targets(project_root, ticket, settings={})
            discovered = payload.get("paths_discovered") or []
            self.assertIn("backend/src/main", discovered)
            self.assertIn("frontend/src", discovered)
            files = payload.get("files") or []
            self.assertIn("backend/src/main/java/App.java", files)

    def test_rlm_targets_explicit_mode_ignores_discovery(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-targets-explicit-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-EXP"
            write_active_feature(project_root, ticket)

            (workspace / "backend" / "src" / "main" / "java").mkdir(parents=True, exist_ok=True)
            (workspace / "backend" / "src" / "main" / "java" / "App.java").write_text(
                "class App {}\n",
                encoding="utf-8",
            )
            (workspace / "custom" / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "custom" / "src" / "app.py").write_text("class Custom:\n    pass\n", encoding="utf-8")
            _write_prd_hints(project_root, ticket, paths=["custom/src"])

            payload = rlm_targets.build_targets(project_root, ticket, settings={"targets_mode": "explicit"})
            self.assertEqual(payload.get("targets_mode"), "explicit")
            self.assertEqual(payload.get("paths_discovered"), [])
            files = payload.get("files") or []
            self.assertIn("custom/src/app.py", files)
            self.assertNotIn("backend/src/main/java/App.java", files)

    def test_rlm_targets_cli_override_explicit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-targets-override-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-OVR"
            write_active_feature(project_root, ticket)

            (workspace / "backend" / "src" / "main" / "java").mkdir(parents=True, exist_ok=True)
            (workspace / "backend" / "src" / "main" / "java" / "App.java").write_text(
                "class App {}\n",
                encoding="utf-8",
            )
            (workspace / "custom" / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "custom" / "src" / "app.py").write_text("class Custom:\n    pass\n", encoding="utf-8")
            _write_prd_hints(project_root, ticket, paths=["custom/src"])

            payload = rlm_targets.build_targets(
                project_root,
                ticket,
                settings={"targets_mode": "auto"},
                targets_mode="explicit",
            )
            self.assertEqual(payload.get("targets_mode"), "explicit")
            self.assertEqual(payload.get("paths_discovered"), [])
            files = payload.get("files") or []
            self.assertIn("custom/src/app.py", files)
            self.assertNotIn("backend/src/main/java/App.java", files)

    def test_rlm_targets_paths_override_limits_scope(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-targets-paths-override-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-OVR-PATHS"
            write_active_feature(project_root, ticket)

            (workspace / "backend" / "src" / "main" / "java").mkdir(parents=True, exist_ok=True)
            (workspace / "backend" / "src" / "main" / "java" / "App.java").write_text(
                "class App {}\n",
                encoding="utf-8",
            )
            (workspace / "custom" / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "custom" / "src" / "app.py").write_text("class Custom:\n    pass\n", encoding="utf-8")

            plan = project_root / "docs" / "plan" / f"{ticket}.md"
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text(
                "## AIDD:FILES_TOUCHED\n- backend/src/main/java/App.java — demo\n",
                encoding="utf-8",
            )
            _write_prd_hints(project_root, ticket, paths=["backend/src/main"])

            payload = rlm_targets.build_targets(
                project_root,
                ticket,
                settings={"targets_mode": "auto"},
                paths_override=["custom/src"],
            )
            self.assertEqual(payload.get("targets_mode"), "explicit")
            self.assertEqual(payload.get("paths"), ["custom/src"])
            self.assertEqual(payload.get("paths_discovered"), [])
            files = payload.get("files") or []
            self.assertIn("custom/src/app.py", files)
            self.assertNotIn("backend/src/main/java/App.java", files)

    def test_rlm_targets_excludes_aidd_docs_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rlm-targets-exclude-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "RLM-3"
            write_active_feature(project_root, ticket)

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "app.py").write_text("class App:\n    pass\n", encoding="utf-8")
            (workspace / "aidd" / "docs" / "prd").mkdir(parents=True, exist_ok=True)
            (workspace / "aidd" / "docs" / "plan").mkdir(parents=True, exist_ok=True)
            _write_prd_hints(project_root, ticket, paths=["aidd/docs/prd", "src"], keywords=["App"])

            settings = {
                "exclude_path_prefixes": ["aidd/docs", "aidd/reports", "aidd/.cache"],
            }
            payload = rlm_targets.build_targets(project_root, ticket, settings=settings)
            paths = payload.get("paths") or []
            discovered = payload.get("paths_discovered") or []
            self.assertIn("src", paths)
            self.assertNotIn("aidd/docs/prd", paths)
            self.assertNotIn("aidd/docs/plan", discovered)


if __name__ == "__main__":
    unittest.main()

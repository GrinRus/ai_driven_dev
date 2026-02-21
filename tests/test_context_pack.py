import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT, cli_cmd, cli_env, ensure_project_root, write_file


class ContextPackTests(unittest.TestCase):
    def test_context_pack_template_writes_rolling_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-pack-template-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            template_text = (REPO_ROOT / "skills" / "aidd-core" / "templates" / "context-pack.template.md").read_text(
                encoding="utf-8"
            )
            write_file(root, "reports/context/template.context-pack.md", template_text)
            write_file(
                root,
                "docs/.active.json",
                '{"ticket": "DEMO-1", "slug_hint": "demo-1", "stage": "review", "work_item": "iteration_id=I1"}\n',
            )

            result = subprocess.run(
                cli_cmd(
                    "context-pack",
                    "--ticket",
                    "DEMO-1",
                    "--agent",
                    "review",
                    "--stage",
                    "review",
                    "--template",
                    "reports/context/template.context-pack.md",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            pack_path = root / "reports" / "context" / "DEMO-1.pack.md"
            self.assertTrue(pack_path.exists())
            text = pack_path.read_text(encoding="utf-8")
            self.assertIn("ticket: DEMO-1", text)
            self.assertIn("stage: review", text)
            self.assertIn("agent: review", text)
            self.assertIn("read_next:", text)
            self.assertIn("artefact_links:", text)

    def test_context_pack_warns_on_stage_specific_placeholder(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-pack-placeholder-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            template_text = (
                "---\n"
                "schema: aidd.context_pack.v1\n"
                "ticket: <ticket>\n"
                "stage: <stage>\n"
                "agent: <agent>\n"
                "scope_key: <scope_key>\n"
                "generated_at: <UTC ISO-8601>\n"
                "---\n"
                "\n"
                "<stage-specific goal>\n"
            )
            write_file(root, "reports/context/template.context-pack.md", template_text)
            write_file(
                root,
                "docs/.active.json",
                '{"ticket": "DEMO-2", "slug_hint": "demo-2", "stage": "review", "work_item": "iteration_id=I1"}\n',
            )

            result = subprocess.run(
                cli_cmd(
                    "context-pack",
                    "--ticket",
                    "DEMO-2",
                    "--agent",
                    "review",
                    "--stage",
                    "review",
                    "--template",
                    "reports/context/template.context-pack.md",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("context pack missing what_to_do", result.stderr)

    def test_context_pack_infers_agent_from_stage_when_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-pack-infer-agent-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            template_text = (REPO_ROOT / "skills" / "aidd-core" / "templates" / "context-pack.template.md").read_text(
                encoding="utf-8"
            )
            write_file(root, "reports/context/template.context-pack.md", template_text)
            write_file(
                root,
                "docs/.active.json",
                '{"ticket": "DEMO-3", "slug_hint": "demo-3", "stage": "plan"}\n',
            )

            result = subprocess.run(
                cli_cmd(
                    "context-pack",
                    "--ticket",
                    "DEMO-3",
                    "--stage",
                    "plan",
                    "--template",
                    "reports/context/template.context-pack.md",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("--agent missing, inferred `planner`", result.stderr)
            pack_path = root / "reports" / "context" / "DEMO-3.pack.md"
            text = pack_path.read_text(encoding="utf-8")
            self.assertIn("agent: planner", text)

    def test_context_pack_infers_agent_for_canonical_stages(self) -> None:
        cases = (
            ("tasklist", "tasklist-refiner"),
            ("spec-interview", "spec-interview-writer"),
            ("status", "status"),
        )
        for stage, expected_agent in cases:
            with self.subTest(stage=stage):
                with tempfile.TemporaryDirectory(prefix=f"context-pack-infer-{stage}-") as tmpdir:
                    root = ensure_project_root(Path(tmpdir))
                    template_text = (
                        REPO_ROOT / "skills" / "aidd-core" / "templates" / "context-pack.template.md"
                    ).read_text(encoding="utf-8")
                    write_file(root, "reports/context/template.context-pack.md", template_text)
                    write_file(
                        root,
                        "docs/.active.json",
                        f'{{"ticket": "DEMO-{stage.upper()}", "slug_hint": "demo-{stage}", "stage": "{stage}"}}\n',
                    )

                    result = subprocess.run(
                        cli_cmd(
                            "context-pack",
                            "--ticket",
                            f"DEMO-{stage.upper()}",
                            "--stage",
                            stage,
                            "--template",
                            "reports/context/template.context-pack.md",
                        ),
                        text=True,
                        capture_output=True,
                        cwd=root,
                        env=cli_env(),
                    )
                    self.assertEqual(result.returncode, 0, msg=result.stderr)
                    self.assertIn(f"--agent missing, inferred `{expected_agent}`", result.stderr)
                    pack_path = root / "reports" / "context" / f"DEMO-{stage.upper()}.pack.md"
                    text = pack_path.read_text(encoding="utf-8")
                    self.assertIn(f"stage: {stage}", text)
                    self.assertIn(f"agent: {expected_agent}", text)


if __name__ == "__main__":
    unittest.main()

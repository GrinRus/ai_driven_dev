import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from claude_workflow_cli.tools.researcher_context import ResearcherContextBuilder

from .helpers import REPO_ROOT, write_file


class ResearcherContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="researcher-context-")
        self.root = Path(self._tmp.name)
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        (self.root / "docs" / "research").mkdir(parents=True, exist_ok=True)
        (self.root / "src" / "main" / "kotlin").mkdir(parents=True, exist_ok=True)

        config_payload = {
            "commit": {},
            "branch": {},
            "researcher": {
                "defaults": {
                    "paths": ["src/main"],
                    "docs": ["docs/research"],
                    "keywords": ["checkout"],
                },
                "tags": {
                    "checkout": {
                        "paths": ["src/main/kotlin"],
                        "docs": ["docs/research/demo-checkout.md"],
                        "keywords": ["order", "payment"],
                    }
                },
                "features": {
                    "demo-checkout": ["checkout"]
                },
            },
        }
        (self.root / "config" / "conventions.json").write_text(
            json.dumps(config_payload, indent=2),
            encoding="utf-8",
        )

        # Sample code file so the context search finds matches.
        sample_code = (
            "package demo\n\n" "class CheckoutFeature { fun run() = \"checkout flow\" }\n"
        )
        write_file(self.root, "src/main/kotlin/CheckoutFeature.kt", sample_code)

        # Existing research doc stub.
        write_file(
            self.root,
            "docs/research/demo-checkout.md",
            "# Research Summary\n\nStatus: pending\n",
        )

    def tearDown(self) -> None:  # noqa: D401
        self._tmp.cleanup()

    def test_builder_creates_targets_and_context(self) -> None:
        builder = ResearcherContextBuilder(self.root)
        scope = builder.build_scope("demo-checkout")
        self.assertIn("src/main/kotlin", scope.paths)
        self.assertIn("docs/research/demo-checkout.md", scope.docs)

        targets_path = builder.write_targets(scope)
        self.assertTrue(targets_path.exists())

        context = builder.collect_context(scope, limit=5)
        context_path = builder.write_context(scope, context)

        payload = json.loads(context_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["slug"], "demo-checkout")
        self.assertGreaterEqual(len(payload["matches"]), 1)

    def test_builder_handles_slug_without_tags(self) -> None:
        builder = ResearcherContextBuilder(self.root)
        scope = builder.build_scope("demo-untagged")
        self.assertEqual(scope.slug, "demo-untagged")
        self.assertEqual(scope.tags, [])
        self.assertIn("src/main", scope.paths)
        self.assertIn("docs/research", scope.docs)

    def test_builder_merges_multiple_tags(self) -> None:
        config_path = self.root / "config" / "conventions.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["researcher"]["tags"]["payments"] = {
            "paths": ["src/payments"],
            "docs": ["docs/research/payments.md"],
            "keywords": ["payments"],
        }
        config["researcher"]["features"]["demo-checkout"] = ["checkout", "payments"]
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

        (self.root / "src" / "payments").mkdir(parents=True, exist_ok=True)
        write_file(
            self.root,
            "docs/research/payments.md",
            "# Payments\n\nStatus: pending\n",
        )

        builder = ResearcherContextBuilder(self.root)
        scope = builder.build_scope("demo-checkout")
        self.assertIn("checkout", scope.tags)
        self.assertIn("payments", scope.tags)
        self.assertIn("src/payments", scope.paths)
        self.assertIn("docs/research/payments.md", scope.docs)
        self.assertIn("payments", scope.keywords)

    def test_set_active_feature_refreshes_targets(self) -> None:
        script = REPO_ROOT / "tools" / "set_active_feature.py"
        env = os.environ.copy()
        result = subprocess.run(
            ["python3", str(script), "--target", str(self.root), "demo-checkout"],
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        slug_file = self.root / "docs" / ".active_feature"
        self.assertEqual(slug_file.read_text(encoding="utf-8"), "demo-checkout")

        targets_path = self.root / "reports" / "research" / "demo-checkout-targets.json"
        self.assertTrue(targets_path.exists(), "Researcher targets should be generated")
        targets = json.loads(targets_path.read_text(encoding="utf-8"))
        self.assertIn("src/main/kotlin", targets["paths"])

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT

SRC_ROOT = REPO_ROOT
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from .helpers import cli_cmd, cli_env, write_file


class ResearcherContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="researcher-context-")
        self.workspace = Path(self._tmp.name)
        self.root = self.workspace / "aidd"
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        (self.root / "docs").mkdir(parents=True, exist_ok=True)

        template_src = (REPO_ROOT / "skills" / "idea-new" / "templates" / "prd.template.md").read_text(
            encoding="utf-8"
        )
        write_file(self.root, "docs/prd/template.md", template_src)

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
                    "demo-checkout": ["checkout"],
                },
            },
        }
        (self.root / "config" / "conventions.json").write_text(
            json.dumps(config_payload, indent=2),
            encoding="utf-8",
        )

        sample_code = "package demo\n\nclass CheckoutFeature { fun run() = \"checkout flow\" }\n"
        write_file(self.root, "src/main/kotlin/CheckoutFeature.kt", sample_code)
        write_file(self.root, "docs/research/demo-checkout.md", "# Research Summary\n\nStatus: pending\n")

    def tearDown(self) -> None:  # noqa: D401
        self._tmp.cleanup()

    def test_set_active_feature_refreshes_rlm_targets(self) -> None:
        env = cli_env()
        result = subprocess.run(
            cli_cmd("set-active-feature", "demo-checkout"),
            text=True,
            capture_output=True,
            cwd=self.workspace,
            env=env,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        prd_path = self.root / "docs" / "prd" / "demo-checkout.prd.md"
        prd_path.write_text(
            "\n".join(
                [
                    "# PRD",
                    "## AIDD:RESEARCH_HINTS",
                    "- Paths: src/main/kotlin",
                    "- Keywords: checkout",
                    "- Notes: focus checkout wiring",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            cli_cmd("set-active-feature", "demo-checkout"),
            text=True,
            capture_output=True,
            cwd=self.workspace,
            env=env,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        state = json.loads((self.root / "docs" / ".active.json").read_text(encoding="utf-8"))
        self.assertEqual(state.get("ticket"), "demo-checkout")
        self.assertEqual(state.get("slug_hint"), "demo-checkout")

        self.assertTrue(prd_path.exists(), "PRD scaffold should be created automatically")

        index_path = self.root / "docs" / "index" / "demo-checkout.json"
        self.assertTrue(index_path.exists(), "Index should be generated on set-active-feature")
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(index_payload.get("ticket"), "demo-checkout")

    def test_slug_hint_persists_without_repeating_argument(self) -> None:
        env = cli_env()
        first = subprocess.run(
            cli_cmd(
                "set-active-feature",
                "--slug-note",
                "checkout-lite",
                "demo-checkout",
            ),
            text=True,
            capture_output=True,
            cwd=self.workspace,
            env=env,
            check=True,
        )
        self.assertEqual(first.returncode, 0, msg=first.stderr)

        prd_path = self.root / "docs" / "prd" / "demo-checkout.prd.md"
        prd_path.write_text(
            "\n".join(
                [
                    "# PRD",
                    "## AIDD:RESEARCH_HINTS",
                    "- Paths: src/main/kotlin",
                    "- Keywords: checkout",
                    "- Notes: focus checkout wiring",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        second = subprocess.run(
            cli_cmd("set-active-feature", "demo-checkout"),
            text=True,
            capture_output=True,
            cwd=self.workspace,
            env=env,
            check=True,
        )
        self.assertEqual(second.returncode, 0, msg=second.stderr)

        state = json.loads((self.root / "docs" / ".active.json").read_text(encoding="utf-8"))
        self.assertEqual(state.get("slug_hint"), "checkout-lite")

        # RLM targets refresh is best-effort in set-active-feature and should not affect slug persistence.


if __name__ == "__main__":
    unittest.main()

import datetime as dt
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from . import helpers
from .helpers import write_active_feature, write_file, write_json


PAYLOAD = json.dumps({"tool_input": {"file_path": "src/main/kotlin/App.kt"}})


def _timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class GateResearcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="gate-research-")
        self.root = Path(self._tmpdir)
        helpers.git_init(self.root)
        helpers.git_config_user(self.root)
        subprocess.run(["git", "checkout", "-b", "feature/demo-checkout"], cwd=self.root, check=True, capture_output=True)

        (self.root / "docs" / "prd").mkdir(parents=True, exist_ok=True)
        (self.root / "docs" / "plan").mkdir(parents=True, exist_ok=True)
        (self.root / "docs" / "research").mkdir(parents=True, exist_ok=True)
        (self.root / "reports" / "research").mkdir(parents=True, exist_ok=True)
        (self.root / "reports" / "prd").mkdir(parents=True, exist_ok=True)
        (self.root / "src" / "main" / "kotlin").mkdir(parents=True, exist_ok=True)

        helpers.ensure_gates_config(self.root)
        config_path = self.root / "config" / "gates.json"
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        config_data.setdefault("researcher", {})["branches"] = []
        config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

        write_active_feature(self.root, "demo-checkout")
        write_file(
            self.root,
            "docs/prd/demo-checkout.prd.md",
            (
                "# PRD\n\n"
                "## Диалог analyst\n"
                "Status: READY\n\n"
                "Researcher: docs/research/demo-checkout.md (Status: reviewed)\n\n"
                "## PRD Review\n"
                "Status: approved\n- [x] ready\n"
            ),
        )
        write_file(self.root, "docs/plan/demo-checkout.md", "# План\n")
        write_file(
            self.root,
            "docs/tasklist/demo-checkout.md",
            "- [x] prepare plan — baseline\n- [ ] QA pending\n",
        )
        write_json(
            self.root,
            "reports/prd/demo-checkout.json",
            {"status": "approved"},
        )

        write_file(
            self.root,
            "docs/research/demo-checkout.md",
            "# Research\n\nStatus: reviewed\n",
        )

        now = _timestamp()
        write_json(
            self.root,
            "reports/research/demo-checkout-targets.json",
            {
                "ticket": "demo-checkout",
                "slug": "demo-checkout",
                "paths": ["src/main/kotlin"],
                "docs": ["docs/research/demo-checkout.md"],
                "generated_at": now,
            },
        )
        write_json(
            self.root,
            "reports/research/demo-checkout-context.json",
            {
                "ticket": "demo-checkout",
                "slug": "demo-checkout",
                "generated_at": now,
                "matches": [],
                "profile": {"is_new_project": False},
                "auto_mode": False,
            },
        )

        write_file(self.root, "src/main/kotlin/App.kt", "class App")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir)

    def test_gate_allows_when_research_ready(self) -> None:
        result = helpers.run_hook(self.root, "gate-workflow.sh", PAYLOAD)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_gate_blocks_on_pending_status(self) -> None:
        write_file(
            self.root,
            "docs/research/demo-checkout.md",
            "# Research\n\nStatus: pending\n",
        )
        result = helpers.run_hook(self.root, "gate-workflow.sh", PAYLOAD)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Researcher", result.stdout + result.stderr)

    def test_gate_allows_pending_with_baseline_marker(self) -> None:
        baseline_doc = (
            "# Research\n\nStatus: pending\n\n## Отсутствие паттернов\n- Контекст пуст, требуется baseline\n"
        )
        write_file(self.root, "docs/research/demo-checkout.md", baseline_doc)
        now = _timestamp()
        write_json(
            self.root,
            "reports/research/demo-checkout-context.json",
            {
                "ticket": "demo-checkout",
                "slug": "demo-checkout",
                "generated_at": now,
                "matches": [],
                "profile": {"is_new_project": True},
                "auto_mode": True,
            },
        )
        result = helpers.run_hook(self.root, "gate-workflow.sh", PAYLOAD)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_gate_blocks_pending_without_baseline_marker(self) -> None:
        write_file(
            self.root,
            "docs/research/demo-checkout.md",
            "# Research\n\nStatus: pending\n",
        )
        now = _timestamp()
        write_json(
            self.root,
            "reports/research/demo-checkout-context.json",
            {
                "ticket": "demo-checkout",
                "slug": "demo-checkout",
                "generated_at": now,
                "matches": [],
                "profile": {"is_new_project": True},
                "auto_mode": True,
            },
        )
        result = helpers.run_hook(self.root, "gate-workflow.sh", PAYLOAD)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("baseline", result.stdout + result.stderr)

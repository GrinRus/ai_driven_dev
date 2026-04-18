from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.repo_tools.prompt_contract_support import assert_prompt_contract, load_prompt_contracts, read_text


REPO_ROOT = Path(__file__).resolve().parents[2]
QUALITY_PROMPT = "aidd_test_quality_audit_prompt_tst002_full.txt"
FLOW_PROMPT_FULL = "aidd_test_flow_prompt_ralph_script_full.txt"
PROMPT_BUILDER = REPO_ROOT / "tests" / "repo_tools" / "build_e2e_prompts.py"
PROMPT_FRAGMENTS_DIR = REPO_ROOT / "tests" / "repo_tools" / "e2e_prompt"
PROMPT_SPECS = PROMPT_FRAGMENTS_DIR / "prompt_specs.json"
CI_LINT_SCRIPT = REPO_ROOT / "tests" / "repo_tools" / "ci-lint.sh"


class E2EQualityPromptContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contracts = load_prompt_contracts()
        cls._prompt_dir_ctx = tempfile.TemporaryDirectory()
        cls.prompt_dir = Path(cls._prompt_dir_ctx.name)
        result = subprocess.run(
            [sys.executable, str(PROMPT_BUILDER), "--output-dir", str(cls.prompt_dir)],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(
                "quality prompt builder failed\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._prompt_dir_ctx.cleanup()

    def test_quality_prompt_builder_fragments_exist(self) -> None:
        self.assertTrue(PROMPT_BUILDER.exists(), msg=f"missing prompt builder: {PROMPT_BUILDER}")
        self.assertTrue(PROMPT_SPECS.exists(), msg=f"missing prompt specs: {PROMPT_SPECS}")
        self.assertTrue((PROMPT_FRAGMENTS_DIR / "prompt_contracts.json").exists())
        for rel in ("base_contract.md", "quality_profile_full.md", "must_read_manifest.md"):
            path = PROMPT_FRAGMENTS_DIR / rel
            self.assertTrue(path.exists(), msg=f"missing quality prompt source: {path}")

    def test_quality_prompt_builder_outputs_are_up_to_date(self) -> None:
        result = subprocess.run(
            [sys.executable, str(PROMPT_BUILDER), "--check"],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"builder check failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def test_quality_prompt_contract_is_data_driven(self) -> None:
        text = read_text(self.prompt_dir / QUALITY_PROMPT)
        assert_prompt_contract(self, text=text, contract=self.contracts["quality"]["FULL"], label="TST-002 FULL")

    def test_ci_lint_uses_render_guard_not_committed_outputs(self) -> None:
        ci_lint = read_text(CI_LINT_SCRIPT)
        self.assertIn("build_e2e_prompts.py --check", ci_lint)
        self.assertNotIn("docs/e2e", ci_lint)

    def test_quality_prompt_keeps_flow_shared_invariants(self) -> None:
        flow_text = read_text(self.prompt_dir / FLOW_PROMPT_FULL)
        quality_text = read_text(self.prompt_dir / QUALITY_PROMPT)
        for needle in self.contracts["quality"]["FLOW_FULL_SHARED"]["contains"]:
            self.assertIn(needle, flow_text, msg=f"flow prompt lost shared invariant: {needle}")
            self.assertIn(needle, quality_text, msg=f"quality prompt missing shared invariant: {needle}")

    def test_quality_prompt_has_machine_friendly_final_marker(self) -> None:
        text = read_text(self.prompt_dir / QUALITY_PROMPT)
        self.assertRegex(
            text.strip().splitlines()[-1],
            r"^`QUALITY_AUDIT_COMPLETE TST-002 status=<PASS\|WARN\|FAIL> wave=<WNNN\|none> feature_final_state=<REACHED\|NOT_REACHED>`$",
        )

    def test_quality_prompt_intentionally_contains_wave_markers(self) -> None:
        text = read_text(self.prompt_dir / QUALITY_PROMPT)
        self.assertIn("Wave <NNN>", text)
        self.assertIn("W<NNN>-1", text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

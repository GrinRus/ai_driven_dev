from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests" / "repo_tools"))
from skill_eval_common import compute_metrics, load_cases  # noqa: E402

RUNNER = REPO_ROOT / "tests" / "repo_tools" / "skill_eval_run.py"
COMPARATOR = REPO_ROOT / "tests" / "repo_tools" / "skill_eval_compare.py"
CASES = REPO_ROOT / "tests" / "repo_tools" / "skill_eval" / "cases.v1.jsonl"


class SkillEvalTests(unittest.TestCase):
    @staticmethod
    def _strong_summary() -> dict:
        return {
            "schema": "aidd.skill_eval.summary.v1",
            "status": "completed",
            "metrics": {
                "macro_trigger_f1": 0.95,
                "exact_match_rate": 0.94,
                "completion_proxy_pass_rate": 0.95,
            },
            "critical_skill_recall": {
                "implement": 0.94,
                "review": 0.93,
                "qa": 0.93,
                "review-spec": 0.92,
                "researcher": 0.92,
            },
        }

    def test_dataset_has_expected_shape(self) -> None:
        rows = load_cases(CASES)
        self.assertEqual(len(rows), 190)
        self.assertEqual(sum(1 for row in rows if row.get("kind") == "positive"), 114)
        self.assertEqual(sum(1 for row in rows if row.get("kind") == "near_miss"), 57)
        self.assertEqual(sum(1 for row in rows if row.get("kind") == "no_skill"), 19)

    def test_compute_metrics_with_fixture(self) -> None:
        rows = [
            {
                "id": "a",
                "kind": "positive",
                "expected_skills": ["implement"],
                "predicted_skill": "implement",
                "completion_proxy_pass": True,
            },
            {
                "id": "b",
                "kind": "positive",
                "expected_skills": ["review"],
                "predicted_skill": "implement",
                "completion_proxy_pass": False,
            },
            {
                "id": "c",
                "kind": "no_skill",
                "expected_skills": [],
                "predicted_skill": "__no_skill__",
                "completion_proxy_pass": True,
            },
        ]
        metrics = compute_metrics(rows, skills=["implement", "review"])
        self.assertAlmostEqual(metrics["exact_match_rate"], 2 / 3, places=6)
        self.assertAlmostEqual(metrics["completion_proxy_pass_rate"], 2 / 3, places=6)
        self.assertIn("implement", metrics["per_skill"])
        self.assertIn("review", metrics["per_skill"])

    def test_runner_skips_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.pop("ANTHROPIC_API_KEY", None)
            env["AIDD_SKILL_EVAL_ENFORCE"] = "0"
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--cases",
                    str(CASES),
                    "--max-cases",
                    "5",
                    "--out-dir",
                    str(Path(tmp) / "events"),
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            summary_files = list((Path(tmp) / "events").glob("run-*/summary.json"))
            self.assertEqual(len(summary_files), 1)
            payload = json.loads(summary_files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "skipped_missing_api_key")

    def test_runner_fails_on_unknown_expected_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad_cases = Path(tmp) / "bad.jsonl"
            bad_cases.write_text(
                json.dumps(
                    {
                        "schema": "aidd.skill_eval.case.v1",
                        "id": "bad-1",
                        "kind": "positive",
                        "prompt": "route this",
                        "expected_skills": ["unknown-skill"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.pop("ANTHROPIC_API_KEY", None)
            env["AIDD_SKILL_EVAL_ENFORCE"] = "0"
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--cases",
                    str(bad_cases),
                    "--out-dir",
                    str(Path(tmp) / "events"),
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown skill", (result.stderr + result.stdout).lower())

    def test_comparator_detects_regression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline.json"
            candidate = Path(tmp) / "candidate.json"
            out = Path(tmp) / "delta.json"

            baseline.write_text(json.dumps(self._strong_summary()), encoding="utf-8")
            candidate.write_text(
                json.dumps(
                    {
                        "schema": "aidd.skill_eval.summary.v1",
                        "status": "completed",
                        "metrics": {
                            "macro_trigger_f1": 0.89,
                            "exact_match_rate": 0.87,
                            "completion_proxy_pass_rate": 0.91,
                        },
                        "critical_skill_recall": {
                            "implement": 0.80,
                            "review": 0.90,
                            "qa": 0.92,
                            "review-spec": 0.90,
                            "researcher": 0.89,
                        },
                    }
                ),
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["AIDD_SKILL_EVAL_ENFORCE"] = "1"
            result = subprocess.run(
                [
                    sys.executable,
                    str(COMPARATOR),
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--out",
                    str(out),
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "failed")
            self.assertTrue(payload.get("findings"))

    def test_comparator_enforced_mode_requires_advisory_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline.json"
            candidate = Path(tmp) / "candidate.json"
            out = Path(tmp) / "delta.json"
            baseline.write_text(json.dumps(self._strong_summary()), encoding="utf-8")
            candidate.write_text(json.dumps(self._strong_summary()), encoding="utf-8")

            env = os.environ.copy()
            env["AIDD_SKILL_EVAL_ENFORCE"] = "1"
            env["AIDD_SKILL_EVAL_ADVISORY_PRS"] = "0"
            env["AIDD_SKILL_EVAL_ADVISORY_DAYS"] = "0"
            env["AIDD_SKILL_EVAL_NIGHTLY_STREAK"] = "0"
            result = subprocess.run(
                [
                    sys.executable,
                    str(COMPARATOR),
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--out",
                    str(out),
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "failed")
            joined = " ".join(payload.get("findings") or []).lower()
            self.assertIn("advisory window", joined)

    def test_comparator_enforced_mode_requires_completed_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline.json"
            candidate = Path(tmp) / "candidate.json"
            out = Path(tmp) / "delta.json"

            baseline.write_text(
                json.dumps(
                    {
                        "schema": "aidd.skill_eval.summary.v1",
                        "status": "skipped_missing_api_key",
                        "metrics": {},
                        "critical_skill_recall": {},
                    }
                ),
                encoding="utf-8",
            )
            candidate.write_text(json.dumps(self._strong_summary()), encoding="utf-8")

            env = os.environ.copy()
            env["AIDD_SKILL_EVAL_ENFORCE"] = "1"
            env["AIDD_SKILL_EVAL_ADVISORY_PRS"] = "10"
            env["AIDD_SKILL_EVAL_ADVISORY_DAYS"] = "14"
            env["AIDD_SKILL_EVAL_NIGHTLY_STREAK"] = "3"
            result = subprocess.run(
                [
                    sys.executable,
                    str(COMPARATOR),
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--out",
                    str(out),
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "failed")
            joined = " ".join(payload.get("findings") or []).lower()
            self.assertIn("baseline status", joined)

    def test_comparator_reports_ready_for_hard_switch_when_window_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline.json"
            candidate = Path(tmp) / "candidate.json"
            out = Path(tmp) / "delta.json"
            baseline.write_text(json.dumps(self._strong_summary()), encoding="utf-8")
            candidate.write_text(json.dumps(self._strong_summary()), encoding="utf-8")

            env = os.environ.copy()
            env["AIDD_SKILL_EVAL_ENFORCE"] = "0"
            env["AIDD_SKILL_EVAL_ADVISORY_PRS"] = "10"
            env["AIDD_SKILL_EVAL_ADVISORY_DAYS"] = "14"
            env["AIDD_SKILL_EVAL_NIGHTLY_STREAK"] = "3"
            result = subprocess.run(
                [
                    sys.executable,
                    str(COMPARATOR),
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--out",
                    str(out),
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "ready_for_hard_switch")


if __name__ == "__main__":
    unittest.main()

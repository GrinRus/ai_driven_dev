from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import (
    cli_cmd,
    cli_env,
    ensure_gates_config,
    ensure_project_root,
    write_active_state,
    write_file,
    write_json,
)


def _quality_path(project_root: Path, ticket: str) -> Path:
    return project_root / "reports" / "observability" / f"{ticket}.context-quality.json"


def _set_ast_binary(project_root: Path, binary_name: str) -> None:
    config_path = project_root / "config" / "conventions.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    ast_cfg = payload.get("ast_index") if isinstance(payload.get("ast_index"), dict) else {}
    ast_cfg["binary"] = binary_name
    payload["ast_index"] = ast_cfg
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class ContextQualityMetricsTests(unittest.TestCase):
    def test_output_contract_materializes_quality_metrics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-quality-output-contract-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            subprocess.run(
                cli_cmd("init"),
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=cli_env(),
            )

            ticket = "CQ-OUT-1"
            scope_key = "iteration_id_I1"
            write_active_state(project_root, ticket=ticket, stage="implement", work_item="iteration_id=I1")
            write_file(project_root, f"docs/prd/{ticket}.prd.md", "# PRD\n")
            write_file(
                project_root,
                f"reports/loops/{ticket}/{scope_key}/stage.implement.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": ticket,
                        "stage": "implement",
                        "scope_key": scope_key,
                        "work_item_key": "iteration_id=I1",
                        "result": "continue",
                        "updated_at": "2024-01-02T00:00:00Z",
                    }
                )
                + "\n",
            )
            actions_log = write_file(
                project_root,
                f"reports/actions/{ticket}/{scope_key}/implement.actions.json",
                "[]\n",
            )
            write_file(
                project_root,
                f"reports/actions/{ticket}/{scope_key}/context-expand.audit.jsonl",
                "\n".join(
                    [
                        json.dumps({"reason_code": "read_outside_readmap"}),
                        json.dumps({"reason_code": "read_outside_readmap"}),
                        json.dumps({"reason_code": "expand_write_boundary"}),
                    ]
                )
                + "\n",
            )

            log_path = project_root / "reports" / "loops" / ticket / "cli.implement.context-quality.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                "\n".join(
                    [
                        "Status: READY",
                        "Work item key: iteration_id=I1",
                        "Artifacts updated: src/demo.py",
                        "Tests: skipped reason_code=manual_skip",
                        "Blockers/Handoff: none",
                        "Next actions: none",
                        f"AIDD:ACTIONS_LOG: {actions_log.relative_to(project_root).as_posix()}",
                        (
                            "AIDD:READ_LOG: "
                            f"aidd/reports/context/{ticket}.pack.md (reason: rolling context); "
                            f"aidd/reports/loops/{ticket}/{scope_key}.loop.pack.md (reason: loop pack); "
                            f"aidd/reports/context/{ticket}-memory-slice.latest.pack.json (reason: memory slice); "
                            f"aidd/docs/prd/{ticket}.prd.md (reason: missing field)"
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                cli_cmd(
                    "output-contract",
                    "--ticket",
                    ticket,
                    "--stage",
                    "implement",
                    "--log",
                    str(log_path),
                    "--format",
                    "json",
                ),
                cwd=workspace,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            output_payload = json.loads(result.stdout)
            self.assertEqual(output_payload.get("status"), "warn")

            quality = json.loads(_quality_path(project_root, ticket).read_text(encoding="utf-8"))
            metrics = quality.get("metrics") or {}
            self.assertGreaterEqual(int(metrics.get("pack_reads") or 0), 2)
            self.assertGreaterEqual(int(metrics.get("slice_reads") or 0), 1)
            self.assertGreaterEqual(int(metrics.get("memory_slice_reads") or 0), 1)
            self.assertGreaterEqual(int(metrics.get("full_reads") or 0), 1)
            self.assertEqual(int(metrics.get("output_contract_total") or 0), 1)
            self.assertGreater(float(metrics.get("output_contract_warn_rate") or 0), 0.0)
            self.assertIn("rg_without_slice_rate", metrics)
            reason_counts = metrics.get("context_expand_count_by_reason") or {}
            self.assertEqual(int(reason_counts.get("read_outside_readmap") or 0), 2)
            self.assertEqual(int(reason_counts.get("expand_write_boundary") or 0), 1)

    def test_research_fallback_updates_fallback_rate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-quality-research-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            subprocess.run(
                cli_cmd("init"),
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=cli_env(),
            )

            ticket = "CQ-RES-1"
            _set_ast_binary(project_root, "ast-index-missing-context-quality")
            write_file(
                project_root,
                f"docs/prd/{ticket}.prd.md",
                "\n".join(
                    [
                        "# PRD",
                        "",
                        "## AIDD:RESEARCH_HINTS",
                        "- Paths: src",
                        "- Keywords: checkout",
                    ]
                )
                + "\n",
            )
            src_dir = workspace / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / "checkout.py").write_text("def checkout_handler():\n    return True\n", encoding="utf-8")

            result = subprocess.run(
                cli_cmd("research", "--ticket", ticket, "--auto"),
                cwd=workspace,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            quality = json.loads(_quality_path(project_root, ticket).read_text(encoding="utf-8"))
            metrics = quality.get("metrics") or {}
            self.assertGreaterEqual(int(metrics.get("retrieval_events") or 0), 1)
            self.assertGreaterEqual(int(metrics.get("fallback_events") or 0), 1)
            self.assertGreater(float(metrics.get("fallback_rate") or 0), 0.0)

    def test_research_check_updates_plan_path_metrics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-quality-research-check-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            subprocess.run(
                cli_cmd("init"),
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=cli_env(),
            )

            ticket = "CQ-PLAN-1"
            ensure_gates_config(project_root, overrides={"ast_index": {"mode": "off", "required": False}})
            write_active_state(project_root, ticket=ticket, stage="plan")
            write_file(project_root, f"docs/research/{ticket}.md", "# Research\n\nStatus: reviewed\n")
            write_file(project_root, "src/main/kotlin/App.kt", "class App {}\n")
            write_json(
                project_root,
                f"reports/research/{ticket}-rlm-targets.json",
                {
                    "ticket": ticket,
                    "files": ["src/main/kotlin/App.kt"],
                    "paths": ["src/main/kotlin"],
                    "paths_discovered": [],
                    "generated_at": "2026-02-25T00:00:00Z",
                },
            )
            write_json(
                project_root,
                f"reports/research/{ticket}-rlm-manifest.json",
                {
                    "ticket": ticket,
                    "files": [
                        {
                            "file_id": "file-app",
                            "path": "src/main/kotlin/App.kt",
                            "rev_sha": "rev-app",
                            "lang": "kt",
                            "size": 10,
                            "prompt_version": "v1",
                        }
                    ],
                },
            )
            write_json(
                project_root,
                f"reports/research/{ticket}-rlm.worklist.pack.json",
                {
                    "schema": "aidd.report.pack.v1",
                    "type": "rlm-worklist",
                    "status": "ready",
                    "entries": [],
                },
            )
            write_file(
                project_root,
                f"reports/research/{ticket}-rlm.nodes.jsonl",
                '{"node_kind":"file","file_id":"file-app","id":"file-app","path":"src/main/kotlin/App.kt","rev_sha":"rev-app"}\n',
            )
            write_file(
                project_root,
                f"reports/research/{ticket}-rlm.links.jsonl",
                '{"link_kind":"import","source":"file-app","target":"file-app","id":"link-1"}\n',
            )
            write_json(project_root, f"reports/research/{ticket}-rlm.links.stats.json", {"links_total": 1})
            write_json(
                project_root,
                f"reports/research/{ticket}-rlm.pack.json",
                {"schema": "aidd.report.pack.v1", "type": "rlm", "status": "ready"},
            )

            result = subprocess.run(
                cli_cmd("research-check", "--ticket", ticket),
                cwd=workspace,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            quality = json.loads(_quality_path(project_root, ticket).read_text(encoding="utf-8"))
            metrics = quality.get("metrics") or {}
            self.assertGreaterEqual(int(metrics.get("pack_reads") or 0), 1)
            self.assertGreaterEqual(int(metrics.get("full_reads") or 0), 2)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Run a Codex-native AIDD live audit by orchestrating existing repo tools."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / ".claude-plugin").is_dir() and (candidate / "skills").is_dir():
            return candidate
    return here.parents[2]


REPO_ROOT = _repo_root()
BUILD_E2E_PROMPTS = REPO_ROOT / "tests" / "repo_tools" / "build_e2e_prompts.py"
STAGE_LAUNCHER = REPO_ROOT / "tests" / "repo_tools" / "aidd_stage_launcher.py"
AIDD_AUDIT_RUNNER = REPO_ROOT / "tests" / "repo_tools" / "aidd_audit_runner.py"
ARTIFACT_AUDIT = REPO_ROOT / "skills" / "aidd-observability" / "runtime" / "artifact_audit.py"

FULL_STAGE_SEQUENCE = (
    ("00_status", "/feature-dev-aidd:status {ticket}", 300),
    ("01_idea_new", "/feature-dev-aidd:idea-new {ticket} {idea_note}", 900),
    ("02_research", "/feature-dev-aidd:researcher {ticket}", 1800),
    ("03_plan_new", "/feature-dev-aidd:plan-new {ticket}", 900),
    ("04_review_spec", "/feature-dev-aidd:review-spec {ticket}", 1200),
    ("05_tasks_new", "/feature-dev-aidd:tasks-new {ticket}", 900),
    ("06_implement", "/feature-dev-aidd:implement {ticket}", 3600),
    ("07_review", "/feature-dev-aidd:review {ticket}", 1800),
    ("08_qa", "/feature-dev-aidd:qa {ticket}", 1800),
)
SMOKE_STAGE_SEQUENCE = FULL_STAGE_SEQUENCE[:6]
FAIL_FAST_EXIT_REASONS = {
    12: "no_space_left_on_device",
    14: "cwd_wrong",
}
ROOT_CAUSE_ACTIONS = {
    "plugin_not_loaded": "Open Codex from the project workspace with the feature-dev-aidd plugin loaded, then rerun the audit.",
    "cwd_wrong": "Rerun from the workspace root, not from the plugin checkout or cache path.",
    "no_space_left_on_device": "Free at least 1 GiB in the workspace filesystem before rerunning the audit.",
    "prompt_fixtures_out_of_date": "Regenerate docs/e2e outputs with tests/repo_tools/build_e2e_prompts.py before trusting live audit results.",
    "readiness_gate_failed": "Inspect the review-spec artifacts and close readiness blockers before retrying downstream stages.",
    "rollup_failed": "Inspect rollup.stdout.txt and rollup.stderr.txt, then repair the audit runner output before trusting the run verdict.",
    "stage_execution_failed": "Inspect the failing stage launcher stdout/stderr capture and step summary before retrying the run.",
    "artifact_audit_failed": "Inspect artifact_audit.stdout.txt and artifact_audit.stderr.txt, then rerun the artifact audit before trusting artifact quality.",
}


class StageSpec(NamedTuple):
    step: str
    stage_command: str
    budget_seconds: int


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_idea_note(ticket: str, raw_note: str | None) -> str:
    note = str(raw_note or "").strip()
    if note:
        return note
    return (
        f"Codex native AIDD quality audit for {ticket}. "
        "Keep scope in the AIDD repo and produce audit-ready artifacts without auto-fix."
    )


def resolve_workspace_layout(raw_project_dir: Path) -> tuple[Path, Path]:
    candidate = raw_project_dir.expanduser().resolve()
    if candidate.name == "aidd" and (candidate / "docs").exists():
        return candidate.parent, candidate
    nested = candidate / "aidd"
    if nested.is_dir() and (nested / "docs").exists():
        return candidate, nested
    return candidate, candidate


def build_stage_specs(*, ticket: str, profile: str, idea_note: str) -> list[StageSpec]:
    templates = FULL_STAGE_SEQUENCE if profile == "full" else SMOKE_STAGE_SEQUENCE
    return [
        StageSpec(
            step=step,
            stage_command=template.format(ticket=ticket, idea_note=idea_note),
            budget_seconds=budget,
        )
        for step, template, budget in templates
    ]


def command_env(plugin_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_dir)
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(plugin_dir) if not current_pythonpath else f"{plugin_dir}:{current_pythonpath}"
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    return env


def read_kv_file(path: Path) -> dict[str, str]:
    payload: dict[str, str] = {}
    if not path.exists():
        return payload
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        payload[key.strip()] = value.strip()
    return payload


def _run_subprocess(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)


def _write_command_capture(run_dir: Path, name: str, result: subprocess.CompletedProcess[str]) -> None:
    (run_dir / f"{name}.stdout.txt").write_text(result.stdout or "", encoding="utf-8")
    (run_dir / f"{name}.stderr.txt").write_text(result.stderr or "", encoding="utf-8")


def _parse_json_stdout(result: subprocess.CompletedProcess[str], *, name: str) -> dict[str, Any]:
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{name} returned invalid JSON on stdout") from exc


def _stage_paths(audit_dir: Path, step: str, run: int) -> dict[str, Path]:
    prefix = f"{step}_run{run}"
    return {
        "summary": audit_dir / f"{prefix}.summary.txt",
        "init_check": audit_dir / f"{prefix}.init_check.txt",
        "disk_preflight": audit_dir / f"{prefix}.disk_preflight.txt",
    }


def _collect_stage_findings(rollup: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    steps = rollup.get("steps") or {}
    stage_classifications: dict[str, dict[str, Any]] = {}
    primary_root_causes: list[str] = []
    for step, payload in sorted(steps.items()):
        if not isinstance(payload, dict):
            continue
        stage_classifications[step] = {
            "classification": payload.get("classification"),
            "classification_subtype": payload.get("classification_subtype"),
            "effective_classification": payload.get("effective_classification"),
            "top_level_status": payload.get("top_level_status"),
            "summary_path": payload.get("summary_path"),
        }
        root_cause = str(payload.get("primary_root_cause") or "").strip()
        if root_cause and root_cause not in primary_root_causes:
            primary_root_causes.append(root_cause)
    return stage_classifications, primary_root_causes


def _artifact_next_actions(payload: dict[str, Any]) -> list[str]:
    return [str(item).strip() for item in payload.get("recommended_next_actions") or [] if str(item).strip()]


def _root_cause_next_actions(root_causes: list[str], fail_fast_reason: str) -> list[str]:
    actions: list[str] = []
    for raw in ([fail_fast_reason] if fail_fast_reason else []) + root_causes:
        subtype = raw.split(":", 1)[-1] if ":" in raw else raw
        hint = ROOT_CAUSE_ACTIONS.get(subtype)
        if hint and hint not in actions:
            actions.append(hint)
    return actions


def _overall_status(*, rollup: dict[str, Any] | None, artifact_gate: str, fail_fast_reason: str) -> str:
    if fail_fast_reason:
        return "FAIL"
    if artifact_gate == "FAIL":
        return "FAIL"
    if rollup:
        for payload in (rollup.get("steps") or {}).values():
            if not isinstance(payload, dict):
                continue
            classification = str(payload.get("classification") or "").strip().upper()
            if classification in {"ENV_BLOCKER", "ENV_MISCONFIG", "PROMPT_EXEC_ISSUE", "CONTRACT_MISMATCH", "FLOW_BUG"}:
                return "WARN"
    if artifact_gate == "WARN":
        return "WARN"
    return "PASS"


def _severity_from_stage(payload: dict[str, Any]) -> str:
    classification = str(payload.get("classification") or "").strip().upper()
    if classification in {"ENV_BLOCKER", "ENV_MISCONFIG", "PROMPT_EXEC_ISSUE", "CONTRACT_MISMATCH", "FLOW_BUG"}:
        return "error"
    return "warn"


def _should_include_stage_finding(payload: dict[str, Any]) -> bool:
    effective = str(payload.get("effective_classification") or payload.get("classification") or "").strip()
    if not effective:
        return False
    return not (effective.startswith("INFO(") or effective.startswith("PENDING("))


def build_top_findings(
    *,
    rollup: dict[str, Any] | None,
    artifact_audit: dict[str, Any],
    fail_fast_reason: str,
    limit: int,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if fail_fast_reason:
        findings.append(
            {
                "severity": "error",
                "source": "launcher",
                "title": fail_fast_reason,
                "summary": ROOT_CAUSE_ACTIONS.get(fail_fast_reason, fail_fast_reason),
            }
        )
    if rollup:
        for step, payload in sorted((rollup.get("steps") or {}).items()):
            if not isinstance(payload, dict):
                continue
            if not _should_include_stage_finding(payload):
                continue
            effective = str(payload.get("effective_classification") or "").strip()
            if not effective:
                continue
            findings.append(
                {
                    "severity": _severity_from_stage(payload),
                    "source": "stage_rollup",
                    "step": step,
                    "title": effective,
                    "summary": str(payload.get("primary_root_cause") or effective),
                    "path": str(payload.get("summary_path") or ""),
                }
            )
    for check in artifact_audit.get("truth_checks") or []:
        if not isinstance(check, dict):
            continue
        findings.append(
            {
                "severity": str(check.get("severity") or "warn"),
                "source": "artifact_audit",
                "title": str(check.get("code") or "artifact_issue"),
                "summary": str(check.get("summary") or ""),
                "paths": check.get("paths") or [],
            }
        )
    severity_order = {"error": 0, "warn": 1}
    findings.sort(key=lambda item: (severity_order.get(str(item.get("severity") or "warn"), 9), str(item.get("title") or "")))
    return findings[:limit]


def render_summary_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Codex E2E Live Audit",
        "",
        f"- Run ID: `{payload['run_id']}`",
        f"- Ticket: `{payload['ticket']}`",
        f"- Profile: `{payload['profile']}`",
        f"- Quality profile: `{payload['quality_profile']}`",
        f"- Overall status: `{payload['status']}`",
        f"- Rollup outcome: `{payload.get('rollup_outcome') or 'n/a'}`",
        f"- Artifact quality gate: `{payload['artifact_quality_gate']}`",
        "",
        "## Run/log verdict",
    ]
    stage_classifications = payload.get("stage_classifications") or {}
    if stage_classifications:
        for step, item in sorted(stage_classifications.items()):
            lines.append(
                "- "
                + f"`{step}` -> `{item.get('effective_classification') or item.get('classification')}` "
                + f"(top-level: `{item.get('top_level_status') or 'n/a'}`)"
            )
    else:
        lines.append("- No stage summary artifacts were produced before the audit stopped.")
    lines.extend(["", "## Warn/Error triage"])
    top_findings = payload.get("top_findings") or []
    if top_findings:
        for finding in top_findings:
            summary = str(finding.get("summary") or "").strip()
            title = str(finding.get("title") or "").strip()
            source = str(finding.get("source") or "").strip()
            lines.append(f"- `{source}` `{title}`: {summary}")
    else:
        lines.append("- No qualifying findings.")
    lines.extend(
        [
            "",
            "## Artifact quality verdict",
            f"- Missing expected reports: {len(payload.get('missing_expected_reports') or [])}",
            f"- Template leakage findings: {len(payload.get('template_leakage') or [])}",
            f"- Status drift findings: {len(payload.get('status_drift') or [])}",
            "",
            "## Next actions",
        ]
    )
    next_actions = payload.get("next_actions") or []
    if next_actions:
        for item in next_actions:
            lines.append(f"- {item}")
    else:
        lines.append("- No follow-up action required.")
    return "\n".join(lines).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Codex-native AIDD live audit using existing repo tools.")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--plugin-dir", required=True)
    parser.add_argument("--ticket", required=True)
    parser.add_argument("--profile", choices=("full", "smoke"), default="smoke")
    parser.add_argument("--quality-profile", choices=("full", "smoke"), default="full")
    parser.add_argument("--idea-note", default="")
    parser.add_argument("--mode", choices=("stream-json", "text"), default="stream-json")
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--min-free-bytes", type=int, default=1_073_741_824)
    parser.add_argument("--top-findings-limit", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plugin_dir = Path(args.plugin_dir).expanduser().resolve()
    workspace_root, aidd_root = resolve_workspace_layout(Path(args.project_dir))
    run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    run_dir = aidd_root / "reports" / "events" / "codex-e2e-audit" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    env = command_env(plugin_dir)
    idea_note = _normalize_idea_note(str(args.ticket), args.idea_note)
    stage_specs = build_stage_specs(ticket=str(args.ticket), profile=str(args.profile), idea_note=idea_note)
    executed_steps: list[str] = []
    fail_fast_reason = ""
    stop_reason = ""

    manifest = {
        "schema": "aidd.codex_e2e_live_audit.run_manifest.v1",
        "generated_at": utc_timestamp(),
        "run_id": run_id,
        "ticket": str(args.ticket),
        "profile": str(args.profile),
        "quality_profile": str(args.quality_profile),
        "workspace_root": str(workspace_root),
        "artifact_root": str(aidd_root),
        "plugin_dir": str(plugin_dir),
        "mode": str(args.mode),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    prompt_check = _run_subprocess(
        [sys.executable, str(BUILD_E2E_PROMPTS), "--check"],
        cwd=plugin_dir,
        env=env,
    )
    _write_command_capture(run_dir, "build_e2e_prompts_check", prompt_check)
    prompt_fixtures_ok = prompt_check.returncode == 0
    if not prompt_fixtures_ok:
        fail_fast_reason = "prompt_fixtures_out_of_date"
        stop_reason = "build_e2e_prompts_failed"

    if not fail_fast_reason:
        for stage in stage_specs:
            executed_steps.append(stage.step)
            launcher_cmd = [
                sys.executable,
                str(STAGE_LAUNCHER),
                "--project-dir",
                str(workspace_root),
                "--plugin-dir",
                str(plugin_dir),
                "--audit-dir",
                str(run_dir),
                "--step",
                stage.step,
                "--run",
                "1",
                "--ticket",
                str(args.ticket),
                "--stage-command",
                stage.stage_command,
                "--mode",
                str(args.mode),
                "--poll-seconds",
                str(int(args.poll_seconds)),
                "--budget-seconds",
                str(int(stage.budget_seconds)),
                "--min-free-bytes",
                str(int(args.min_free_bytes)),
            ]
            stage_result = _run_subprocess(launcher_cmd, cwd=plugin_dir, env=env)
            _write_command_capture(run_dir, f"{stage.step}.launcher", stage_result)

            if stage_result.returncode in FAIL_FAST_EXIT_REASONS:
                fail_fast_reason = FAIL_FAST_EXIT_REASONS[stage_result.returncode]
                stop_reason = f"launcher_exit_{stage_result.returncode}"
                break

            paths = _stage_paths(run_dir, stage.step, 1)
            init_check = read_kv_file(paths["init_check"])
            if init_check and (
                str(init_check.get("plugins_ok") or "0") != "1"
                or str(init_check.get("slash_ok") or "0") != "1"
            ):
                fail_fast_reason = "plugin_not_loaded"
                stop_reason = f"{stage.step}_plugin_not_loaded"
                break

            if stage_result.returncode != 0:
                fail_fast_reason = "stage_execution_failed"
                stop_reason = f"{stage.step}_returned_{stage_result.returncode}"
                break

    summary_files = sorted(run_dir.glob("*_run*.summary.txt"))
    rollup_payload: dict[str, Any] | None = None
    if summary_files:
        rollup_cmd = [
            sys.executable,
            str(AIDD_AUDIT_RUNNER),
            "rollup",
            "--audit-dir",
            str(run_dir),
            "--project-dir",
            str(workspace_root),
            "--plugin-dir",
            str(plugin_dir),
        ]
        rollup_result = _run_subprocess(rollup_cmd, cwd=plugin_dir, env=env)
        _write_command_capture(run_dir, "rollup", rollup_result)
        if rollup_result.returncode == 0:
            rollup_payload = _parse_json_stdout(rollup_result, name="aidd_audit_runner rollup")
            (run_dir / "rollup.json").write_text(
                json.dumps(rollup_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        elif not fail_fast_reason:
            fail_fast_reason = "rollup_failed"
            stop_reason = "rollup_command_failed"
    else:
        (run_dir / "rollup.json").write_text("{}\n", encoding="utf-8")

    artifact_cmd = [
        sys.executable,
        str(ARTIFACT_AUDIT),
        "--root",
        str(workspace_root),
        "--ticket",
        str(args.ticket),
    ]
    artifact_result = _run_subprocess(artifact_cmd, cwd=plugin_dir, env=env)
    _write_command_capture(run_dir, "artifact_audit", artifact_result)
    if artifact_result.returncode == 0:
        artifact_payload = _parse_json_stdout(artifact_result, name="artifact_audit")
    else:
        if not fail_fast_reason:
            fail_fast_reason = "artifact_audit_failed"
            stop_reason = "artifact_audit_command_failed"
        artifact_payload = {
            "artifact_quality_gate": "FAIL",
            "truth_checks": [],
            "missing_expected_reports": [],
            "template_leakage": [],
            "status_drift": [],
            "recommended_next_actions": ["artifact_audit command failed; inspect artifact_audit.stderr.txt."],
        }
    (run_dir / "artifact_audit.json").write_text(
        json.dumps(artifact_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    stage_classifications, primary_root_causes = _collect_stage_findings(rollup_payload or {})
    next_actions = _root_cause_next_actions(primary_root_causes, fail_fast_reason)
    for item in _artifact_next_actions(artifact_payload):
        if item not in next_actions:
            next_actions.append(item)

    top_limit = int(args.top_findings_limit or 0) or (10 if str(args.quality_profile) == "full" else 5)
    summary_payload = {
        "schema": "aidd.codex_e2e_live_audit.summary.v1",
        "pack_version": "1",
        "generated_at": utc_timestamp(),
        "run_id": run_id,
        "ticket": str(args.ticket),
        "profile": str(args.profile),
        "quality_profile": str(args.quality_profile),
        "status": _overall_status(
            rollup=rollup_payload,
            artifact_gate=str(artifact_payload.get("artifact_quality_gate") or "FAIL"),
            fail_fast_reason=fail_fast_reason,
        ),
        "prompt_fixtures_ok": int(prompt_fixtures_ok),
        "workspace_root": str(workspace_root),
        "artifact_root": str(aidd_root),
        "plugin_dir": str(plugin_dir),
        "audit_dir": str(run_dir),
        "executed_steps": executed_steps,
        "stopped_early": int(bool(stop_reason)),
        "stop_reason": stop_reason,
        "fail_fast_reason": fail_fast_reason,
        "rollup_outcome": (rollup_payload or {}).get("rollup_outcome", ""),
        "stage_classifications": stage_classifications,
        "primary_root_causes": primary_root_causes,
        "artifact_quality_gate": artifact_payload.get("artifact_quality_gate"),
        "missing_expected_reports": artifact_payload.get("missing_expected_reports") or [],
        "template_leakage": artifact_payload.get("template_leakage") or [],
        "status_drift": artifact_payload.get("status_drift") or [],
        "top_findings": build_top_findings(
            rollup=rollup_payload,
            artifact_audit=artifact_payload,
            fail_fast_reason=fail_fast_reason,
            limit=top_limit,
        ),
        "next_actions": next_actions,
    }

    (run_dir / "summary.json").write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "summary.md").write_text(render_summary_markdown(summary_payload), encoding="utf-8")
    print(json.dumps(summary_payload, ensure_ascii=False, indent=2))
    return 0 if summary_payload["status"] in {"PASS", "WARN"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

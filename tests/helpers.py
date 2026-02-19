import json
import os
import pathlib
import shutil
import subprocess
import sys
from typing import Any, Dict, Optional


def _find_repo_root(start: pathlib.Path) -> pathlib.Path:
    for path in [start, *start.parents]:
        if (path / "pyproject.toml").is_file() or (path / ".claude-plugin").is_dir():
            return path
    return start.parents[1]


REPO_ROOT = _find_repo_root(pathlib.Path(__file__).resolve())
PROJECT_SUBDIR = "aidd"
TEMPLATES_ROOT = REPO_ROOT / "templates" / PROJECT_SUBDIR
HOOKS_DIR = REPO_ROOT / "hooks"
DEFAULT_GATES_CONFIG: Dict[str, Any] = {
    "tests_required": "soft",
    "tests_gate": {
        "source_roots": [
            "src/main",
            "src",
            "app",
            "apps",
            "packages",
            "services",
            "service",
            "lib",
            "libs",
            "backend",
            "frontend",
        ],
        "source_extensions": [
            ".kt",
            ".java",
            ".kts",
            ".groovy",
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".go",
            ".rb",
            ".rs",
            ".cs",
            ".php",
        ],
        "test_patterns": [
            "src/test/{rel_dir}/{base}Test{ext}",
            "src/test/{rel_dir}/{base}Tests{ext}",
            "tests/{rel_dir}/test_{base}{ext}",
            "tests/{rel_dir}/{base}_test{ext}",
            "tests/{rel_dir}/{base}.test{ext}",
            "tests/{rel_dir}/{base}.spec{ext}",
            "test/{rel_dir}/test_{base}{ext}",
            "test/{rel_dir}/{base}_test{ext}",
            "spec/{rel_dir}/{base}_spec{ext}",
            "spec/{rel_dir}/{base}Spec{ext}",
            "__tests__/{rel_dir}/{base}.test{ext}",
            "__tests__/{rel_dir}/{base}.spec{ext}",
        ],
        "exclude_dirs": [
            "test",
            "tests",
            "spec",
            "specs",
            "__tests__",
            "androidTest",
            "integrationTest",
            "functionalTest",
            "testFixtures",
        ],
    },
    "deps_allowlist": False,
    "prd_review": {
        "enabled": True,
        "approved_statuses": ["ready"],
        "blocking_statuses": ["blocked"],
        "allow_missing_section": False,
        "require_action_items_closed": True,
        "allow_missing_report": False,
        "blocking_severities": ["critical"],
        "report_path": "aidd/reports/prd/{ticket}.json",
    },
    "plan_review": {
        "enabled": True,
        "approved_statuses": ["ready"],
        "blocking_statuses": ["blocked"],
        "allow_missing_section": False,
        "require_action_items_closed": True,
    },
    "researcher": {
        "enabled": True,
        "branches": ["feature/*", "release/*", "hotfix/*"],
        "skip_branches": ["docs/*"],
        "require_status": ["reviewed"],
        "freshness_days": 14,
        "allow_missing": False,
        "minimum_paths": 1,
        "allow_pending_baseline": True,
        "baseline_phrase": "контекст пуст",
    },
    "rlm": {
        "enabled": True,
        "require_pack": True,
        "require_nodes": True,
        "require_links": True,
        "required_for_langs": ["kt", "kts", "java"],
    },
    "analyst": {
        "enabled": True,
        "branches": ["feature/*", "release/*", "hotfix/*"],
        "skip_branches": ["docs/*"],
        "min_questions": 1,
        "require_ready": True,
        "allow_blocked": False,
        "check_open_questions": True,
        "require_dialog_section": True,
    },
    "qa": {
        "enabled": True,
        "branches": ["feature/*", "release/*", "hotfix/*"],
        "skip_branches": ["docs/*"],
        "command": ["python3", "${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/qa.py"],
        "debounce_minutes": 10,
        "report": "aidd/reports/qa/{ticket}.json",
        "allow_missing_report": False,
        "block_on": ["blocker", "critical"],
        "warn_on": ["major", "minor"],
        "handoff": True,
        "handoff_mode": "block",
        "tests": {
            "allow_skip": True,
            "source": "readme-ci",
            "discover": {
                "max_files": 20,
                "max_bytes": 200000,
                "allow_paths": [
                    ".github/workflows/*.yml",
                    ".github/workflows/*.yaml",
                    ".gitlab-ci.yml",
                    ".circleci/config.yml",
                    "Jenkinsfile",
                    "README*",
                    "readme*",
                ],
            },
        },
    },
    "reviewer": {
        "enabled": True,
        "tests_marker": "aidd/reports/reviewer/{ticket}/{scope_key}.tests.json",
        "tests_field": "tests",
        "required_values": ["required"],
        "optional_values": ["optional", "skipped", "not-required"],
        "warn_on_missing": True,
    },
    "tasklist_spec": {
        "enabled": True,
        "branches": ["feature/*", "release/*", "hotfix/*"],
        "skip_branches": ["docs/*"],
    },
    "tasklist_progress": {
        "enabled": True,
        "code_prefixes": [
            "src/",
            "tests/",
            "test/",
            "app/",
            "services/",
            "backend/",
            "frontend/",
            "lib/",
            "core/",
            "packages/",
            "modules/",
            "cmd/",
        ],
        "skip_branches": ["docs/*", "chore/*"],
        "allow_missing_tasklist": False,
        "override_env": "CLAUDE_SKIP_TASKLIST_PROGRESS",
        "sources": ["implement", "qa", "review", "gate", "handoff"],
    },
}


def hook_path(name: str) -> pathlib.Path:
    return HOOKS_DIR / name


def _project_root(base: pathlib.Path) -> pathlib.Path:
    """Return the project root inside the workspace (always <workspace>/aidd)."""
    if base.name == PROJECT_SUBDIR:
        return base
    return base / PROJECT_SUBDIR


def run_hook(
    tmp_path: pathlib.Path, hook_name: str, payload: str, *, extra_env: Optional[dict[str, str]] = None
) -> subprocess.CompletedProcess[str]:
    """Execute the given hook inside tmp_path and capture output."""
    project_root = _project_root(tmp_path)
    workspace_root = project_root.parent if project_root.name == PROJECT_SUBDIR else project_root
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "docs").mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra_env:
        env.update(extra_env)
    config_src = TEMPLATES_ROOT / "config" / "gates.json"
    config_dst = project_root / "config" / "gates.json"
    if config_src.exists() and not config_dst.exists():
        config_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config_src, config_dst)
    result = subprocess.run(
        [str(hook_path(hook_name))],
        input=payload,
        text=True,
        capture_output=True,
        cwd=project_root,
        env=env,
    )
    return result


def write_file(root: pathlib.Path, relative: str, content: str = "") -> pathlib.Path:
    """Create a file with UTF-8 content."""
    project_root = _project_root(root)
    target = project_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def tasklist_ready_text(ticket: str = "demo-checkout") -> str:
    return (
        "---\n"
        f"Ticket: {ticket}\n"
        "Status: READY\n"
        "Updated: 2024-01-01\n"
        f"Plan: aidd/docs/plan/{ticket}.md\n"
        f"Spec: aidd/docs/spec/{ticket}.spec.yaml\n"
        "---\n\n"
        "## AIDD:CONTEXT_PACK\n"
        "Updated: 2024-01-01\n"
        f"Ticket: {ticket}\n"
        "Stage: implement\n"
        "Status: READY\n\n"
        "### TL;DR\n"
        "- Goal: demo\n"
        "- Current focus (1 checkbox): I1\n"
        "- Done since last pack: none\n"
        "- Risk level: low — none\n\n"
        "### Blockers summary (handoff)\n"
        "- none\n\n"
        "## AIDD:SPEC_PACK\n"
        "Updated: 2024-01-01\n"
        f"Spec: aidd/docs/spec/{ticket}.spec.yaml (status: ready)\n"
        "- Goal: demo\n"
        "- Non-goals:\n"
        "  - none\n"
        "- Key decisions:\n"
        "  - default\n"
        "- Risks:\n"
        "  - low\n\n"
        "## AIDD:TEST_STRATEGY\n"
        "- Unit: smoke\n"
        "- Integration: smoke\n"
        "- Contract: smoke\n"
        "- E2E/Stand: smoke\n"
        "- Test data: fixtures\n\n"
        "## AIDD:TEST_EXECUTION\n"
        "- profile: none\n"
        "- tasks: []\n"
        "- filters: []\n"
        "- when: manual\n"
        "- reason: docs-only\n\n"
        "## AIDD:ITERATIONS_FULL\n"
        "- [ ] I1: Bootstrap (iteration_id: I1)\n"
        "  - Goal: setup baseline\n"
        "  - Outputs: tasklist ready\n"
        "  - DoD: tasklist ready\n"
        "  - Expected paths:\n"
        f"    - docs/tasklist/{ticket}.md\n"
        "  - Size budget:\n"
        "    - max_files: 3\n"
        "    - max_loc: 120\n"
        f"  - Boundaries: docs/tasklist/{ticket}.md\n"
        "  - Steps:\n"
        "    - write tasklist baseline\n"
        "    - verify sections\n"
        "    - confirm gate\n"
        "  - Tests:\n"
        "    - profile: none\n"
        "    - tasks: []\n"
        "    - filters: []\n"
        "  - Acceptance mapping: AC-1\n"
        "  - Risks & mitigations: low → none\n"
        "  - Dependencies: none\n\n"
        "- [ ] I2: Follow-up (iteration_id: I2)\n"
        "  - Goal: follow-up\n"
        "  - Outputs: follow-up tasks\n"
        "  - DoD: tasklist ready\n"
        "  - Expected paths:\n"
        f"    - docs/tasklist/{ticket}.md\n"
        "  - Size budget:\n"
        "    - max_files: 3\n"
        "    - max_loc: 120\n"
        f"  - Boundaries: docs/tasklist/{ticket}.md\n"
        "  - Steps:\n"
        "    - update tasklist\n"
        "    - verify gate\n"
        "    - record progress\n"
        "  - Tests:\n"
        "    - profile: none\n"
        "    - tasks: []\n"
        "    - filters: []\n"
        "  - Acceptance mapping: AC-2\n"
        "  - Risks & mitigations: low → none\n"
        "  - Dependencies: none\n\n"
        "- [ ] I3: Follow-up (iteration_id: I3)\n"
        "  - Goal: follow-up\n"
        "  - Outputs: follow-up tasks\n"
        "  - DoD: tasklist ready\n"
        "  - Expected paths:\n"
        f"    - docs/tasklist/{ticket}.md\n"
        "  - Size budget:\n"
        "    - max_files: 3\n"
        "    - max_loc: 120\n"
        f"  - Boundaries: docs/tasklist/{ticket}.md\n"
        "  - Steps:\n"
        "    - update tasklist\n"
        "    - verify gate\n"
        "    - record progress\n"
        "  - Tests:\n"
        "    - profile: none\n"
        "    - tasks: []\n"
        "    - filters: []\n"
        "  - Acceptance mapping: AC-3\n"
        "  - Risks & mitigations: low → none\n"
        "  - Dependencies: none\n\n"
        "## AIDD:NEXT_3\n"
        "- [ ] I1: Bootstrap (ref: iteration_id=I1)\n"
        "- [ ] I2: Follow-up (ref: iteration_id=I2)\n"
        "- [ ] I3: Follow-up (ref: iteration_id=I3)\n\n"
        "## AIDD:HANDOFF_INBOX\n"
        "<!-- handoff:manual start -->\n"
        "<!-- handoff:manual end -->\n\n"
        "## AIDD:QA_TRACEABILITY\n"
        "- AC-1 → check → met → evidence\n"
        "- AC-2 → check → met → evidence\n\n"
        "## AIDD:CHECKLIST\n"
        "### AIDD:CHECKLIST_QA\n"
        "- [ ] QA: acceptance criteria verified\n\n"
        "## AIDD:PROGRESS_LOG\n"
        "- (empty)\n\n"
        "## AIDD:HOW_TO_UPDATE\n"
        "- update NEXT_3 after each iteration\n"
    )


def spec_ready_text(ticket: str = "demo-checkout") -> str:
    return (
        "schema: aidd.spec.v1\n"
        f"ticket: \"{ticket}\"\n"
        "slug: \"demo\"\n"
        "status: ready\n"
        "updated_at: \"2024-01-01\"\n"
        "sources:\n"
        f"  plan: \"aidd/docs/plan/{ticket}.md\"\n"
        f"  prd: \"aidd/docs/prd/{ticket}.prd.md\"\n"
        f"  tasklist: \"aidd/docs/tasklist/{ticket}.md\"\n"
        f"  interview_log: \"aidd/reports/spec/{ticket}.interview.jsonl\"\n"
        "open_questions:\n"
        "  blocker: []\n"
        "  non_blocker: []\n"
    )


def write_spec_ready(root: pathlib.Path, ticket: str = "demo-checkout") -> pathlib.Path:
    return write_file(root, f"docs/spec/{ticket}.spec.yaml", spec_ready_text(ticket))


def write_tasklist_ready(root: pathlib.Path, ticket: str = "demo-checkout", *, include_spec: bool = True) -> pathlib.Path:
    if include_spec:
        write_spec_ready(root, ticket)
    return write_file(root, f"docs/tasklist/{ticket}.md", tasklist_ready_text(ticket))


def write_json(root: pathlib.Path, relative: str, data: Dict[str, Any]) -> pathlib.Path:
    project_root = _project_root(root)
    target = project_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return target


def _read_active_state(project_root: pathlib.Path) -> Dict[str, Any]:
    path = project_root / "docs" / ".active.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_active_state(
    root: pathlib.Path,
    *,
    ticket: Optional[str] = None,
    slug_hint: Optional[str] = None,
    stage: Optional[str] = None,
    work_item: Optional[str] = None,
) -> None:
    project_root = _project_root(root)
    state = _read_active_state(project_root)
    if ticket is not None:
        state["ticket"] = ticket
    if slug_hint is not None:
        state["slug_hint"] = slug_hint
    if stage is not None:
        state["stage"] = stage
    if work_item is not None:
        state["work_item"] = work_item
    write_file(project_root, "docs/.active.json", json.dumps(state, indent=2) + "\n")


def write_active_feature(root: pathlib.Path, ticket: str, slug_hint: Optional[str] = None) -> None:
    hint = ticket if slug_hint is None else slug_hint
    write_active_state(root, ticket=ticket, slug_hint=hint)


def write_active_stage(root: pathlib.Path, stage: str) -> None:
    write_active_state(root, stage=stage)


def ensure_project_root(root: pathlib.Path) -> pathlib.Path:
    """Ensure workspace has the expected project subdirectory."""
    project_root = root / PROJECT_SUBDIR
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "docs").mkdir(parents=True, exist_ok=True)
    (project_root / "reports").mkdir(parents=True, exist_ok=True)
    (project_root / "config").mkdir(parents=True, exist_ok=True)
    return project_root


def bootstrap_workspace(root: pathlib.Path, *extra_args: str) -> None:
    """Run canonical init wrapper to bootstrap workspace into root."""
    ensure_project_root(root)
    subprocess.run(
        cli_cmd("init", *extra_args),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=root,
        env=cli_env(),
    )


def ensure_gates_config(
    root: pathlib.Path, overrides: Optional[Dict[str, Any]] = None
) -> pathlib.Path:
    config = DEFAULT_GATES_CONFIG.copy()
    if overrides:
        config.update(overrides)
    return write_json(root, "config/gates.json", config)


def git_init(path: pathlib.Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)


def git_config_user(path: pathlib.Path) -> None:
    """Configure default git user for commits inside tests."""
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def cli_cmd(*args: str) -> list[str]:
    """Build a command that invokes the canonical skill entrypoint."""
    if not args:
        return []
    cmd = args[0]
    rest = list(args[1:])
    python_mode = False
    if cmd == "context-gc":
        raise ValueError("context-gc entrypoints unavailable; use hooks/context-gc-*.sh")
    if cmd == "init":
        script = REPO_ROOT / "skills" / "aidd-init" / "runtime" / "init.py"
        python_mode = True
    elif cmd in {"loop-pack", "loop-step", "loop-run", "preflight-prepare", "preflight-result-validate", "output-contract"}:
        loop_runtime_map = {
            "loop-pack": "loop_pack.py",
            "loop-step": "loop_step.py",
            "loop-run": "loop_run.py",
            "preflight-prepare": "preflight_prepare.py",
            "preflight-result-validate": "preflight_result_validate.py",
            "output-contract": "output_contract.py",
        }
        script = REPO_ROOT / "skills" / "aidd-loop" / "runtime" / loop_runtime_map[cmd]
        python_mode = True
    elif cmd in {"analyst-check"}:
        script = REPO_ROOT / "skills" / "idea-new" / "runtime" / "analyst_check.py"
        python_mode = True
    elif cmd in {"research-check"}:
        script = REPO_ROOT / "skills" / "plan-new" / "runtime" / "research_check.py"
        python_mode = True
    elif cmd in {"prd-review"}:
        script = REPO_ROOT / "skills" / "review-spec" / "runtime" / "prd_review_cli.py"
        python_mode = True
    elif cmd == "research":
        script = REPO_ROOT / "skills" / "researcher" / "runtime" / "research.py"
        python_mode = True
    elif cmd in {
        "reports-pack",
        "rlm-nodes-build",
        "rlm-links-build",
        "rlm-jsonl-compact",
        "rlm-finalize",
        "rlm-verify",
    }:
        rlm_runtime_map = {
            "reports-pack": "reports_pack.py",
            "rlm-nodes-build": "rlm_nodes_build.py",
            "rlm-links-build": "rlm_links_build.py",
            "rlm-jsonl-compact": "rlm_jsonl_compact.py",
            "rlm-finalize": "rlm_finalize.py",
            "rlm-verify": "rlm_verify.py",
        }
        script = REPO_ROOT / "skills" / "aidd-rlm" / "runtime" / rlm_runtime_map[cmd]
        python_mode = True
    elif cmd in {"review-pack", "review-report", "reviewer-tests", "context-pack"}:
        review_runtime_map = {
            "review-pack": "review_pack.py",
            "review-report": "review_report.py",
            "reviewer-tests": "reviewer_tests.py",
            "context-pack": "context_pack.py",
        }
        script = REPO_ROOT / "skills" / "review" / "runtime" / review_runtime_map[cmd]
        python_mode = True
    elif cmd in {"qa"}:
        script = REPO_ROOT / "skills" / "qa" / "runtime" / "qa.py"
        python_mode = True
    elif cmd in {"status", "index-sync"}:
        status_runtime_map = {
            "status": "status.py",
            "index-sync": "index_sync.py",
        }
        script = REPO_ROOT / "skills" / "status" / "runtime" / status_runtime_map[cmd]
        python_mode = True
    else:
        docio_runtime_map = {
            "actions-apply": "actions_apply.py",
            "actions-validate": "actions_validate.py",
            "context-expand": "context_expand.py",
            "context-map-validate": "context_map_validate.py",
            "md-patch": "md_patch.py",
            "md-slice": "md_slice.py",
        }
        flow_state_runtime_map = {
            "prd-check": "prd_check.py",
            "progress": "progress_cli.py",
            "set-active-feature": "set_active_feature.py",
            "set-active-stage": "set_active_stage.py",
            "stage-result": "stage_result.py",
            "status-summary": "status_summary.py",
            "tasklist-check": "tasklist_check.py",
            "tasklist-normalize": "tasklist_check.py",
            "tasks-derive": "tasks_derive.py",
        }
        observability_runtime_map = {
            "dag-export": "dag_export.py",
            "doctor": "doctor.py",
            "identifiers": "identifiers.py",
            "tests-log": "tests_log.py",
            "tools-inventory": "tools_inventory.py",
        }
        rlm_runtime_map = {
            "rlm-slice": "rlm_slice.py",
        }
        core_runtime_map = {
            "diff-boundary-check": "diff_boundary_check.py",
            "plan-review-gate": "plan_review_gate.py",
            "prd-review-gate": "prd_review_gate.py",
            "skill-contract-validate": "skill_contract_validate.py",
        }
        if cmd in docio_runtime_map:
            script = REPO_ROOT / "skills" / "aidd-docio" / "runtime" / docio_runtime_map[cmd]
            python_mode = True
        elif cmd in flow_state_runtime_map:
            script = REPO_ROOT / "skills" / "aidd-flow-state" / "runtime" / flow_state_runtime_map[cmd]
            if cmd == "tasklist-normalize":
                rest = ["--fix", *rest]
            python_mode = True
        elif cmd in observability_runtime_map:
            script = REPO_ROOT / "skills" / "aidd-observability" / "runtime" / observability_runtime_map[cmd]
            python_mode = True
        elif cmd in rlm_runtime_map:
            script = REPO_ROOT / "skills" / "aidd-rlm" / "runtime" / rlm_runtime_map[cmd]
            python_mode = True
        elif cmd in core_runtime_map:
            script = REPO_ROOT / "skills" / "aidd-core" / "runtime" / core_runtime_map[cmd]
            python_mode = True
        else:
            raise ValueError(f"unknown canonical CLI command: {cmd}")
    if python_mode:
        return ["python3", str(script), *rest]
    return [str(script), *rest]


def cli_env(extra_env: Optional[dict[str, str]] = None) -> dict[str, str]:
    """Return an environment with CLAUDE_PLUGIN_ROOT wired for canonical entrypoints."""
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
    # Integration tests execute runtime entrypoints from a mutable checkout.
    # Keep plugin write-safety coverage in dedicated unit tests and avoid
    # flaky false positives in subprocess-based workflow tests.
    env.setdefault("AIDD_ALLOW_PLUGIN_WRITES", "1")
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else f"{REPO_ROOT}:{existing_pythonpath}"
    if extra_env:
        env.update(extra_env)
    return env

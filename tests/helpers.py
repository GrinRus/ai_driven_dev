import json
import os
import pathlib
import shutil
import subprocess
import sys
from typing import Any, Dict, Optional


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT_SUBDIR = "aidd"
PAYLOAD_ROOT = REPO_ROOT / "src" / "claude_workflow_cli" / "data" / "payload" / PROJECT_SUBDIR
HOOKS_DIR = PAYLOAD_ROOT / ".claude" / "hooks"
SETTINGS_SRC = REPO_ROOT / "src" / "claude_workflow_cli" / "data" / "payload" / ".claude" / "settings.json"
os.environ.setdefault("CLAUDE_WORKFLOW_PYTHON", sys.executable)
os.environ.setdefault("CLAUDE_WORKFLOW_DEV_SRC", str(REPO_ROOT / "src"))
DEFAULT_GATES_CONFIG: Dict[str, Any] = {
    "feature_ticket_source": "aidd/docs/.active_ticket",
    "feature_slug_hint_source": "aidd/docs/.active_feature",
    "tests_required": "soft",
    "deps_allowlist": False,
    "prd_review": {
        "enabled": True,
        "approved_statuses": ["approved"],
        "blocking_statuses": ["blocked"],
        "allow_missing_section": False,
        "require_action_items_closed": True,
        "allow_missing_report": False,
        "blocking_severities": ["critical"],
        "report_path": "reports/prd/{ticket}.json",
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
        "command": ["claude-workflow", "qa", "--gate"],
        "report": "reports/qa/{ticket}.json",
        "allow_missing_report": False,
        "block_on": ["blocker", "critical"],
        "warn_on": ["major", "minor"],
        "handoff": False,
    },
    "reviewer": {
        "enabled": True,
        "tests_marker": "reports/reviewer/{ticket}.json",
        "tests_field": "tests",
        "required_values": ["required"],
        "optional_values": ["optional", "skipped", "not-required"],
        "warn_on_missing": True,
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


def run_hook(tmp_path: pathlib.Path, hook_name: str, payload: str) -> subprocess.CompletedProcess[str]:
    """Execute the given hook inside tmp_path and capture output."""
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    src_path = REPO_ROOT / "src"
    vendor_path = PAYLOAD_ROOT / ".claude" / "hooks" / "_vendor"
    existing = env.get("PYTHONPATH")
    path_value = str(src_path)
    if vendor_path.exists():
        path_value = f"{vendor_path}:{path_value}"
    if existing:
        path_value = f"{str(src_path)}:{existing}"
    env["PYTHONPATH"] = path_value
    config_src = PAYLOAD_ROOT / "config" / "gates.json"
    config_dst = tmp_path / "config" / "gates.json"
    if config_src.exists() and not config_dst.exists():
        config_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config_src, config_dst)
    scripts_src = PAYLOAD_ROOT / "scripts"
    if scripts_src.exists():
        for file in scripts_src.rglob("*"):
            if not file.is_file():
                continue
            dest = tmp_path / "scripts" / file.relative_to(scripts_src)
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dest)
    settings_dst = tmp_path / ".claude" / "settings.json"
    if SETTINGS_SRC.exists() and not settings_dst.exists():
        settings_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SETTINGS_SRC, settings_dst)
    result = subprocess.run(
        [str(hook_path(hook_name))],
        input=payload,
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
    )
    return result


def write_file(root: pathlib.Path, relative: str, content: str = "") -> pathlib.Path:
    """Create a file with UTF-8 content."""
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def write_json(root: pathlib.Path, relative: str, data: Dict[str, Any]) -> pathlib.Path:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return target


def write_active_feature(root: pathlib.Path, ticket: str, slug_hint: Optional[str] = None) -> None:
    write_file(root, "docs/.active_ticket", ticket)
    hint = ticket if slug_hint is None else slug_hint
    write_file(root, "docs/.active_feature", hint)


def ensure_project_root(root: pathlib.Path) -> pathlib.Path:
    """Ensure workspace has the expected project subdirectory with .claude stub."""
    project_root = root / PROJECT_SUBDIR
    (project_root / ".claude").mkdir(parents=True, exist_ok=True)
    return project_root


def bootstrap_workspace(root: pathlib.Path, *extra_args: str) -> None:
    """Run init-claude-workflow.sh from the packaged payload into root."""
    project_root = ensure_project_root(root)
    env = os.environ.copy()
    env["CLAUDE_TEMPLATE_DIR"] = str(PAYLOAD_ROOT)
    script = PAYLOAD_ROOT / "init-claude-workflow.sh"
    subprocess.run(
        ["bash", str(script), *extra_args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=project_root,
        env=env,
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
    """Build a command that invokes the installed claude-workflow CLI via helper."""
    return [sys.executable, str(PAYLOAD_ROOT / "tools" / "run_cli.py"), *args]

import json
import os
import pathlib
import subprocess
from typing import Any, Dict, Optional


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
DEFAULT_GATES_CONFIG: Dict[str, Any] = {
    "feature_slug_source": "docs/.active_feature",
    "api_contract": True,
    "db_migration": True,
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
        "report_path": "reports/prd/{slug}.json",
    },
    "researcher": {
        "enabled": True,
        "branches": ["feature/*", "release/*", "hotfix/*"],
        "skip_branches": ["docs/*"],
        "require_status": ["reviewed"],
        "freshness_days": 14,
        "allow_missing": False,
        "minimum_paths": 1,
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
    "reviewer": {
        "enabled": True,
        "tests_marker": "reports/reviewer/{slug}.json",
        "tests_field": "tests",
        "required_values": ["required"],
        "optional_values": ["optional", "skipped", "not-required"],
        "warn_on_missing": True,
    },
}


def hook_path(name: str) -> pathlib.Path:
    return HOOKS_DIR / name


def run_hook(tmp_path: pathlib.Path, hook_name: str, payload: str) -> subprocess.CompletedProcess[str]:
    """Execute the given hook inside tmp_path and capture output."""
    env = os.environ.copy()
    src_path = REPO_ROOT / "src"
    existing = env.get("PYTHONPATH")
    path_value = str(src_path)
    if existing:
        path_value = f"{str(src_path)}:{existing}"
    env["PYTHONPATH"] = path_value
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

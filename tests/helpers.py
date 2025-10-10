import json
import pathlib
import subprocess
from typing import Any, Dict


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
DEFAULT_GATES_CONFIG: Dict[str, Any] = {
    "feature_slug_source": "docs/.active_feature",
    "api_contract": True,
    "db_migration": True,
    "tests_required": "soft",
    "deps_allowlist": False,
}


def hook_path(name: str) -> pathlib.Path:
    return HOOKS_DIR / name


def run_hook(tmp_path: pathlib.Path, hook_name: str, payload: str) -> subprocess.CompletedProcess[str]:
    """Execute the given hook inside tmp_path and capture output."""
    result = subprocess.run(
        [str(hook_path(hook_name))],
        input=payload,
        text=True,
        capture_output=True,
        cwd=tmp_path,
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


def ensure_gates_config(root: pathlib.Path, overrides: Dict[str, Any] | None = None) -> pathlib.Path:
    config = DEFAULT_GATES_CONFIG.copy()
    if overrides:
        config.update(overrides)
    return write_json(root, "config/gates.json", config)


def git_init(path: pathlib.Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)

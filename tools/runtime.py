from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, Optional

from tools import active_state as _active_state
from tools.feature_ids import FeatureIdentifiers, read_active_state, resolve_identifiers
from tools.resources import DEFAULT_PROJECT_SUBDIR, resolve_project_root as resolve_workspace_root

DEFAULT_REVIEW_REPORT = "aidd/reports/reviewer/{ticket}/{scope_key}.json"
_SCOPE_KEY_RE = re.compile(r"[^A-Za-z0-9_.-]+")


try:
    VERSION = metadata.version("aidd-runtime")
except metadata.PackageNotFoundError:  # pragma: no cover - editable installs
    VERSION = "0.1.0"


def require_plugin_root() -> Path:
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.environ.get("AIDD_PLUGIN_DIR")
    if not raw:
        raise RuntimeError("CLAUDE_PLUGIN_ROOT (or AIDD_PLUGIN_DIR) is required to run AIDD tools.")
    plugin_root = Path(raw).expanduser().resolve()
    os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(plugin_root))
    return plugin_root


def _plugin_workspace_guard(workspace_root: Path) -> None:
    if os.environ.get("AIDD_ALLOW_PLUGIN_WORKSPACE", "").strip() == "1":
        return
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.environ.get("AIDD_PLUGIN_DIR")
    if not raw:
        return
    plugin_root = Path(raw).expanduser().resolve()
    if workspace_root != plugin_root:
        return
    if not (plugin_root / ".claude-plugin").exists():
        return
    raise RuntimeError(
        "refusing to use plugin repository as workspace root for runtime artifacts; "
        "run commands from the project workspace root."
    )


def resolve_roots(raw_target: Path | None = None, *, create: bool = False) -> tuple[Path, Path]:
    target = (raw_target or Path.cwd()).resolve()
    workspace_root, project_root = resolve_workspace_root(target, DEFAULT_PROJECT_SUBDIR)
    _plugin_workspace_guard(workspace_root)
    if project_root.exists():
        return workspace_root, project_root
    if create:
        project_root.mkdir(parents=True, exist_ok=True)
        return workspace_root, project_root
    if not workspace_root.exists():
        raise FileNotFoundError(f"workspace directory {workspace_root} does not exist")
    raise FileNotFoundError(
        f"workflow not found at {project_root}. Run '/feature-dev-aidd:aidd-init' or "
        f"'${{CLAUDE_PLUGIN_ROOT}}/tools/init.sh' from the workspace root "
        f"(templates install into ./{DEFAULT_PROJECT_SUBDIR})."
    )


def require_workflow_root(raw_target: Path | None = None) -> tuple[Path, Path]:
    workspace_root, project_root = resolve_roots(raw_target, create=False)
    if (project_root / "docs").exists():
        return workspace_root, project_root
    raise FileNotFoundError(
        f"workflow files not found at {project_root}/docs; "
        f"bootstrap via '/feature-dev-aidd:aidd-init' or "
        f"'${{CLAUDE_PLUGIN_ROOT}}/tools/init.sh' from the workspace root "
        f"(templates install into ./{DEFAULT_PROJECT_SUBDIR})."
    )


def resolve_claude_dir(target: Path) -> Path:
    candidate = target / ".claude"
    if candidate.exists():
        return candidate
    if target.name == DEFAULT_PROJECT_SUBDIR:
        return target.parent / ".claude"
    return candidate


def resolve_feature_context(
    target: Path,
    *,
    ticket: Optional[str] = None,
    slug_hint: Optional[str] = None,
) -> FeatureIdentifiers:
    return resolve_identifiers(target, ticket=ticket, slug_hint=slug_hint)


def require_ticket(
    target: Path,
    *,
    ticket: Optional[str] = None,
    slug_hint: Optional[str] = None,
) -> tuple[str, FeatureIdentifiers]:
    context = resolve_feature_context(target, ticket=ticket, slug_hint=slug_hint)
    resolved = (context.resolved_ticket or "").strip()
    if not resolved:
        raise ValueError(
            "feature ticket is required; pass --ticket or set docs/.active.json via /feature-dev-aidd:idea-new."
        )
    return resolved, context


def auto_index_enabled() -> bool:
    raw = os.getenv("AIDD_INDEX_AUTO", "").strip().lower()
    if not raw:
        return True
    return raw not in {"0", "false", "no", "off"}


def resolve_path_for_target(path: Path, target: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    parts = path.parts
    if parts and parts[0] == ".":
        path = Path(*parts[1:])
        parts = path.parts
    if parts and parts[0] == DEFAULT_PROJECT_SUBDIR and target.name == DEFAULT_PROJECT_SUBDIR:
        path = Path(*parts[1:])
    return (target / path).resolve()


def rel_path(path: Path, root: Path) -> str:
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
    if root.name == DEFAULT_PROJECT_SUBDIR:
        return f"{DEFAULT_PROJECT_SUBDIR}/{rel}"
    return rel


def detect_branch(target: Path) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=target,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return None
    if proc.returncode != 0:
        return None
    branch = proc.stdout.strip()
    if not branch or branch.upper() == "HEAD":
        return None
    return branch


def sanitize_scope_key(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    cleaned = _SCOPE_KEY_RE.sub("_", raw)
    cleaned = cleaned.strip("._-")
    return cleaned or ""


def is_valid_work_item_key(value: str | None) -> bool:
    return _active_state.is_valid_work_item_key(value)


def is_iteration_work_item_key(value: str | None) -> bool:
    return _active_state.is_iteration_work_item_key(value)


def resolve_scope_key(work_item_key: Optional[str], ticket: str, *, fallback: str = "ticket") -> str:
    scope = sanitize_scope_key(work_item_key or "")
    if scope:
        return scope
    scope = sanitize_scope_key(ticket or "")
    return scope or fallback


def read_active_work_item(target: Path) -> str:
    state = read_active_state(target)
    return (state.work_item or "").strip()


def read_active_last_review_report_id(target: Path) -> str:
    state = read_active_state(target)
    return (state.last_review_report_id or "").strip()


def read_active_stage(target: Path) -> str:
    state = read_active_state(target)
    return (state.stage or "").strip().lower()


def read_active_ticket(target: Path) -> str:
    state = read_active_state(target)
    ticket = (state.ticket or "").strip()
    if ticket:
        return ticket
    return (state.slug_hint or "").strip()


def read_active_slug(target: Path) -> str:
    state = read_active_state(target)
    return (state.slug_hint or "").strip()


def load_json_file(path: Path) -> Dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to parse {path}: {exc}") from exc


def format_ticket_label(context: FeatureIdentifiers, fallback: str = "активной фичи") -> str:
    ticket = (context.resolved_ticket or "").strip() or fallback
    if context.slug_hint and context.slug_hint.strip() and context.slug_hint.strip() != ticket:
        return f"{ticket} (slug hint: {context.slug_hint.strip()})"
    return ticket


def settings_path(target: Path) -> Path:
    return resolve_claude_dir(target) / "settings.json"


def load_settings_json(target: Path) -> dict:
    settings_file = settings_path(target)
    if not settings_file.exists():
        return {}
    try:
        return json.loads(settings_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"cannot parse {settings_file}: {exc}") from exc


def load_tests_settings(target: Path) -> dict:
    settings = load_settings_json(target)
    automation = settings.get("automation") or {}
    tests_cfg = automation.get("tests")
    return tests_cfg if isinstance(tests_cfg, dict) else {}


def normalize_checkpoint_triggers(value: object) -> list[str]:
    if value is None:
        return ["progress"]
    if isinstance(value, (list, tuple)):
        items = [str(item).strip().lower() for item in value if str(item).strip()]
    else:
        items = [item.strip().lower() for item in str(value).replace(",", " ").split() if item.strip()]
    return items or ["progress"]


def maybe_write_test_checkpoint(
    target: Path,
    ticket: Optional[str],
    slug_hint: Optional[str],
    source: str,
) -> None:
    if not ticket:
        return
    tests_cfg = load_tests_settings(target)
    cadence = str(tests_cfg.get("cadence") or "on_stop").strip().lower()
    if cadence != "checkpoint":
        return
    triggers = normalize_checkpoint_triggers(
        tests_cfg.get("checkpointTrigger") or tests_cfg.get("checkpoint_trigger")
    )
    if "progress" not in triggers:
        return
    checkpoint_path = target / ".cache" / "test-checkpoint.json"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ticket": ticket,
        "slug_hint": slug_hint or ticket,
        "trigger": "progress",
        "source": source,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    checkpoint_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def maybe_sync_index(
    target: Path,
    ticket: Optional[str],
    slug_hint: Optional[str],
    *,
    reason: str = "",
    announce: bool = False,
) -> None:
    if not auto_index_enabled():
        return
    if not ticket:
        return
    ticket = str(ticket).strip()
    if not ticket:
        return
    slug = (slug_hint or ticket).strip() or ticket
    try:
        from tools import index_sync as _index_sync

        index_path = _index_sync.write_index(target, ticket, slug)
        if announce:
            rel = rel_path(index_path, target)
            print(f"[index] index saved to {rel}.")
    except Exception as exc:
        label = f" ({reason})" if reason else ""
        print(f"[index] warning{label}: failed to update index ({exc}).", file=sys.stderr)


def load_gates_config(target: Path) -> dict:
    config_path = target / "config" / "gates.json"
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def reviewer_gate_config(target: Path) -> dict:
    tests_cfg = load_tests_settings(target)
    reviewer_cfg = tests_cfg.get("reviewerGate") if isinstance(tests_cfg, dict) else None
    return reviewer_cfg if isinstance(reviewer_cfg, dict) else {}


def review_report_template(target: Path) -> str:
    config = load_gates_config(target)
    reviewer_cfg = config.get("reviewer") if isinstance(config, dict) else None
    if not isinstance(reviewer_cfg, dict):
        reviewer_cfg = {}
    template = str(
        reviewer_cfg.get("review_report")
        or reviewer_cfg.get("report")
        or DEFAULT_REVIEW_REPORT
    )
    if "{scope_key}" not in template:
        return DEFAULT_REVIEW_REPORT
    return template


def is_relative_to(path: Path, ancestor: Path) -> bool:
    try:
        path.relative_to(ancestor)
        return True
    except ValueError:
        return False


def reviewer_marker_path(
    target: Path,
    template: str,
    ticket: str,
    slug_hint: Optional[str],
    *,
    scope_key: Optional[str] = None,
) -> Path:
    rel_text = template.replace("{ticket}", ticket)
    if "{slug}" in template:
        rel_text = rel_text.replace("{slug}", slug_hint or ticket)
    if "{scope_key}" in template:
        resolved_scope = resolve_scope_key(scope_key, ticket)
        rel_text = rel_text.replace("{scope_key}", resolved_scope)
    marker_path = resolve_path_for_target(Path(rel_text), target)
    target_root = target.resolve()
    if not is_relative_to(marker_path, target_root):
        raise ValueError(
            f"reviewer marker path {marker_path} escapes project root {target_root}"
        )
    ensure_reviewer_marker_migrated(marker_path)
    return marker_path


def _looks_like_review_report(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    kind = str(payload.get("kind") or "").strip().lower()
    stage = str(payload.get("stage") or "").strip().lower()
    if kind == "review" or stage == "review":
        return True
    if "findings" in payload or "blocking_findings_count" in payload:
        return True
    return False


def ensure_reviewer_marker_migrated(marker_path: Path) -> bool:
    if marker_path.exists():
        return False
    if not marker_path.name.endswith(".tests.json"):
        return False
    old_path = marker_path.with_name(marker_path.name.replace(".tests.json", ".json"))
    if not old_path.exists():
        return False
    try:
        payload = json.loads(old_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if _looks_like_review_report(payload):
        return False
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        old_path.unlink()
    except OSError:
        return False
    return True


def resolve_tool_result_id(payload: Dict[str, Any], *, index: Optional[int] = None) -> tuple[str, str]:
    raw_id = str(payload.get("id") or "").strip()
    if raw_id:
        return raw_id, ""
    request_id = str(payload.get("request_id") or payload.get("requestId") or "").strip()
    if request_id:
        fallback = f"tool_result:{request_id}"
    elif index is not None:
        fallback = f"tool_result:{index}"
    else:
        fallback = "tool_result:unknown"
    warn = f"tool_result_missing_id request_id={request_id or 'n/a'}"
    return fallback, warn

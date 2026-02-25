from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from aidd_runtime import stage_lexicon
from aidd_runtime.diff_boundary_check import extract_boundaries, matches_pattern, parse_front_matter
from hooks.hooklib import read_stage, read_ticket, resolve_hooks_mode

ALWAYS_ALLOW_PATTERNS = ["aidd/reports/**", "aidd/reports/actions/**"]
MEMORY_READ_PATTERNS = [
    "aidd/reports/memory/*.semantic.pack.json",
    "aidd/reports/memory/*.decisions.pack.json",
    "aidd/reports/memory/*.decisions.jsonl",
]

_SCOPE_KEY_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_STAGE_RESULT_SUFFIXES = (
    "/stage.implement.result.json",
    "/stage.review.result.json",
    "/stage.qa.result.json",
)
_MANUAL_PREFLIGHT_RE = re.compile(
    r"\bpython(?:3)?\b[^\n\r]*\bskills/aidd-loop/runtime/preflight_prepare\.py\b",
    flags=re.IGNORECASE,
)


def _sanitize_scope_key(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    cleaned = _SCOPE_KEY_RE.sub("_", raw)
    cleaned = cleaned.strip("._-")
    return cleaned or ""


def _resolve_scope_key(ticket: str, work_item_key: str) -> str:
    scope = _sanitize_scope_key(work_item_key)
    if scope:
        return scope
    scope = _sanitize_scope_key(ticket)
    return scope or "ticket"


def _read_active_payload(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_tool_path(path_value: str, project_dir: Path, aidd_root: Optional[Path]) -> Path:
    raw = Path(path_value)
    if raw.is_absolute():
        return raw.resolve()

    candidates: list[Path] = []
    if path_value.startswith("aidd/"):
        if aidd_root and aidd_root.name == "aidd":
            candidates.append((aidd_root.parent / raw).resolve())
        else:
            candidates.append((project_dir / raw).resolve())
    else:
        candidates.append((project_dir / raw).resolve())
        if aidd_root:
            candidates.append((aidd_root / raw).resolve())

    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate.resolve()
        except Exception:
            continue
    if candidates:
        return candidates[0]
    return (project_dir / raw).resolve()


def _path_candidates(path: Path, project_dir: Path, aidd_root: Optional[Path]) -> list[str]:
    normalized: list[str] = []

    def _add(value: str) -> None:
        candidate = value.replace("\\", "/").strip()
        if not candidate:
            return
        if candidate.startswith("./"):
            candidate = candidate[2:]
        if candidate not in normalized:
            normalized.append(candidate)

    _add(path.as_posix())

    try:
        rel_project = path.relative_to(project_dir).as_posix()
        _add(rel_project)
        if project_dir.name == "aidd":
            _add(f"aidd/{rel_project}")
    except Exception:
        pass

    if aidd_root:
        try:
            rel_aidd = path.relative_to(aidd_root).as_posix()
            _add(rel_aidd)
            _add(f"aidd/{rel_aidd}")
        except Exception:
            pass

    return normalized


def _load_json_map(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_loop_allowed_paths(loop_pack_path: Path) -> list[str]:
    if not loop_pack_path.exists():
        return []
    try:
        lines = loop_pack_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    allowed, _forbidden = extract_boundaries(parse_front_matter(lines))
    deduped: list[str] = []
    for item in allowed:
        value = str(item or "").strip()
        if value and value not in deduped:
            deduped.append(value)
    return deduped


def _matches_any_pattern(candidates: list[str], patterns: list[str]) -> bool:
    for pattern in patterns:
        raw_pattern = str(pattern or "").strip()
        if not raw_pattern:
            continue
        for candidate in candidates:
            if matches_pattern(candidate, raw_pattern):
                return True
    return False


def _tool_input_path(tool_input: Dict[str, Any]) -> str:
    for key in ("file_path", "path", "filename", "file", "pattern"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _normalize_candidate(value: str) -> str:
    normalized = str(value or "").replace("\\", "/").strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _glob_candidates(tool_input: Dict[str, Any], project_dir: Path, aidd_root: Optional[Path]) -> list[str]:
    candidates: list[str] = []

    def _add(raw: str) -> None:
        normalized = _normalize_candidate(raw)
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    base_raw = str(tool_input.get("path") or "").strip()
    pattern_raw = str(tool_input.get("pattern") or "").strip()

    if base_raw:
        base_path = resolve_tool_path(base_raw, project_dir, aidd_root)
        for item in _path_candidates(base_path, project_dir, aidd_root):
            _add(item)

    if pattern_raw:
        _add(pattern_raw)
        if base_raw and not Path(pattern_raw).is_absolute():
            _add((Path(base_raw) / pattern_raw).as_posix())

    return candidates


def _policy_state(project_dir: Path, aidd_root: Optional[Path]) -> Dict[str, Any]:
    root = aidd_root or project_dir
    active_path = root / "docs" / ".active.json"
    ticket = read_ticket(active_path, active_path) or ""
    stage = read_stage(active_path) or ""
    active_payload = _read_active_payload(active_path)
    work_item_key = str(active_payload.get("work_item") or "").strip()
    scope_key = _resolve_scope_key(ticket, work_item_key)

    if not ticket or not stage:
        return {}

    context_base = root / "reports" / "context" / ticket
    readmap_path = context_base / f"{scope_key}.readmap.json"
    writemap_path = context_base / f"{scope_key}.writemap.json"
    loop_pack_path = root / "reports" / "loops" / ticket / f"{scope_key}.loop.pack.md"

    readmap = _load_json_map(readmap_path)
    writemap = _load_json_map(writemap_path)

    read_allowed = []
    if isinstance(readmap.get("allowed_paths"), list):
        read_allowed.extend(str(item) for item in readmap.get("allowed_paths") if str(item).strip())
    if isinstance(readmap.get("loop_allowed_paths"), list):
        read_allowed.extend(str(item) for item in readmap.get("loop_allowed_paths") if str(item).strip())
    read_allowed.extend(_extract_loop_allowed_paths(loop_pack_path))
    if isinstance(readmap.get("always_allow"), list):
        read_allowed.extend(str(item) for item in readmap.get("always_allow") if str(item).strip())
    read_allowed.extend(ALWAYS_ALLOW_PATTERNS)
    read_allowed.extend(MEMORY_READ_PATTERNS)

    write_allowed = []
    if isinstance(writemap.get("allowed_paths"), list):
        write_allowed.extend(str(item) for item in writemap.get("allowed_paths") if str(item).strip())
    if isinstance(writemap.get("loop_allowed_paths"), list):
        write_allowed.extend(str(item) for item in writemap.get("loop_allowed_paths") if str(item).strip())
    write_allowed.extend(_extract_loop_allowed_paths(loop_pack_path))
    if isinstance(writemap.get("always_allow"), list):
        write_allowed.extend(str(item) for item in writemap.get("always_allow") if str(item).strip())
    write_allowed.extend(ALWAYS_ALLOW_PATTERNS)

    docops_only = []
    if isinstance(writemap.get("docops_only_paths"), list):
        docops_only.extend(str(item) for item in writemap.get("docops_only_paths") if str(item).strip())

    return {
        "root": root,
        "ticket": ticket,
        "stage": stage,
        "scope_key": scope_key,
        "work_item_key": work_item_key,
        "readmap_path": readmap_path,
        "writemap_path": writemap_path,
        "readmap_exists": readmap_path.exists(),
        "writemap_exists": writemap_path.exists(),
        "read_allowed": read_allowed,
        "write_allowed": write_allowed,
        "docops_only": docops_only,
    }


def _is_tasklist_or_context_pack(candidates: list[str]) -> bool:
    prefixes = (
        "docs/tasklist/",
        "aidd/docs/tasklist/",
        "reports/context/",
        "aidd/reports/context/",
    )
    for candidate in candidates:
        if any(candidate.startswith(prefix) for prefix in prefixes):
            return True
    return False


def _always_allow(candidates: list[str]) -> bool:
    return _matches_any_pattern(candidates, ALWAYS_ALLOW_PATTERNS)


def _is_loop_stage_result_write(candidates: list[str]) -> bool:
    for candidate in candidates:
        normalized = f"/{_normalize_candidate(candidate)}"
        if "/reports/loops/" not in normalized:
            continue
        if any(normalized.endswith(suffix) for suffix in _STAGE_RESULT_SUFFIXES):
            return True
    return False


def _deny_or_warn(strict: bool, *, reason: str, system_message: str) -> Dict[str, str]:
    if strict:
        return {"decision": "deny", "reason": reason, "system_message": system_message}
    return {"decision": "allow", "reason": reason, "system_message": system_message}


def _canonical_stage_rerun_hint(stage: str, ticket: str) -> str:
    normalized_stage = stage_lexicon.resolve_stage_name(stage)
    normalized_ticket = str(ticket or "").strip()
    if stage_lexicon.is_loop_stage(normalized_stage):
        if normalized_ticket:
            return f"/feature-dev-aidd:{normalized_stage} {normalized_ticket}"
        return f"/feature-dev-aidd:{normalized_stage} <ticket>"
    if normalized_ticket:
        return f"/feature-dev-aidd:status {normalized_ticket}"
    return "/feature-dev-aidd:status <ticket>"


def manual_preflight_bash_decision(
    *,
    command: str,
    project_dir: Path,
    aidd_root: Optional[Path],
) -> Optional[Dict[str, str]]:
    if not _MANUAL_PREFLIGHT_RE.search(command):
        return None

    state = _policy_state(project_dir, aidd_root)
    stage = str(state.get("stage") or "").strip()
    ticket = str(state.get("ticket") or "").strip()
    hint = _canonical_stage_rerun_hint(stage, ticket)
    strict_mode = resolve_hooks_mode() == "strict"
    return _deny_or_warn(
        strict_mode,
        reason="Loop stage policy: manual stage-chain preflight invocation is forbidden.",
        system_message=(
            "Loop stage policy: direct `python3 .../skills/aidd-loop/runtime/preflight_prepare.py` "
            "invocation is forbidden. Re-run canonical stage command "
            f"`{hint}`; stage-chain will regenerate preflight artifacts automatically."
        ),
    )


def _docops_only_violation(candidates: list[str], state: Dict[str, Any]) -> bool:
    docops_only = state.get("docops_only") or []
    if not isinstance(docops_only, list) or not docops_only:
        return False
    return _matches_any_pattern(candidates, [str(item) for item in docops_only])


def enforce_rw_policy(
    *,
    tool_name: str,
    tool_input: Dict[str, Any],
    project_dir: Path,
    aidd_root: Optional[Path],
) -> Optional[Dict[str, str]]:
    if tool_name not in {"Read", "Write", "Edit", "Glob"}:
        return None

    if tool_name == "Glob":
        candidates = _glob_candidates(tool_input, project_dir, aidd_root)
        if not candidates:
            return None
    else:
        path_value = _tool_input_path(tool_input)
        if not path_value:
            return None
        path = resolve_tool_path(path_value, project_dir, aidd_root)
        candidates = _path_candidates(path, project_dir, aidd_root)
    strict_mode = resolve_hooks_mode() == "strict"

    state = _policy_state(project_dir, aidd_root)
    if not state:
        return None

    stage = stage_lexicon.resolve_stage_name(str(state.get("stage") or ""))
    loop_stage = stage_lexicon.is_loop_stage(stage)
    planning_stage = stage_lexicon.is_planning_stage(stage)

    if tool_name in {"Write", "Edit"} and loop_stage and _is_loop_stage_result_write(candidates):
        return _deny_or_warn(
            strict_mode,
            reason="Loop stage stage-result files are runtime-owned.",
            system_message=(
                "Loop stage policy: direct Edit/Write to stage.*.result.json is forbidden. "
                "Use canonical stage runtime/stage-chain to emit stage results."
            ),
        )

    if _always_allow(candidates):
        if tool_name in {"Write", "Edit"} and loop_stage:
            if _is_tasklist_or_context_pack(candidates) or _docops_only_violation(candidates, state):
                return _deny_or_warn(
                    strict_mode,
                    reason="Loop stage writes to DocOps-only paths must go through actions.",
                    system_message=(
                        "Loop stage policy: direct Edit/Write to DocOps-only paths is forbidden. "
                        "Use actions + DocOps (`python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/actions_apply.py`)."
                    ),
                )
        return None

    if tool_name in {"Read", "Glob"} and loop_stage:
        if not state.get("readmap_exists"):
            return _deny_or_warn(
                strict_mode,
                reason="Missing readmap for loop stage. Run preflight first.",
                system_message=(
                    "No readmap found for current loop scope. Re-run canonical loop stage command "
                    "(`/feature-dev-aidd:implement <ticket>`, `/feature-dev-aidd:review <ticket>`, "
                    "or `/feature-dev-aidd:qa <ticket>`); stage-chain will regenerate preflight artifacts "
                    "before reading additional files."
                ),
            )
        allowed = state.get("read_allowed") or []
        if not _matches_any_pattern(candidates, allowed):
            return _deny_or_warn(
                strict_mode,
                reason="Read is outside readmap/allowed_paths.",
                system_message=(
                    "Read is outside readmap/allowed_paths. Use `context-expand` "
                    "("
                    "`python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/context_expand.py --path <path> "
                    "--reason-code <code> --reason <text>`"
                    ") to request progressive disclosure."
                ),
            )

    if tool_name in {"Write", "Edit"}:
        if loop_stage and (_is_tasklist_or_context_pack(candidates) or _docops_only_violation(candidates, state)):
            return _deny_or_warn(
                strict_mode,
                reason="Loop stage writes to DocOps-only paths must go through actions.",
                system_message=(
                    "Loop stage policy: direct Edit/Write to DocOps-only paths is forbidden. "
                    "Use actions + DocOps (`python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/actions_apply.py`)."
                ),
            )

        if loop_stage:
            if not state.get("writemap_exists"):
                return _deny_or_warn(
                    strict_mode,
                    reason="Missing writemap for loop stage. Run preflight first.",
                    system_message=(
                        "No writemap found for current loop scope. Re-run canonical loop stage command "
                        "(`/feature-dev-aidd:implement <ticket>`, `/feature-dev-aidd:review <ticket>`, "
                        "or `/feature-dev-aidd:qa <ticket>`); stage-chain will regenerate preflight artifacts "
                        "before writing files."
                    ),
                )
            allowed = state.get("write_allowed") or []
            if not _matches_any_pattern(candidates, allowed):
                return _deny_or_warn(
                    strict_mode,
                    reason="Write is outside writemap.",
                    system_message=(
                        "Write is outside writemap. Use `context-expand` "
                        "("
                        "`python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/context_expand.py --expand-write --path <path> "
                        "--reason-code <code> --reason <text>`"
                        ") to expand boundaries."
                    ),
                )

        if planning_stage and state.get("writemap_exists"):
            allowed = state.get("write_allowed") or []
            if not _matches_any_pattern(candidates, allowed):
                return _deny_or_warn(
                    strict_mode,
                    reason="Write is outside planning-stage writemap.",
                    system_message=(
                        "Planning-stage write is outside writemap/contract. "
                        "Expand with `context-expand` "
                        "("
                        "`python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/context_expand.py --expand-write ...` "
                        ") "
                        "or update stage contract."
                    ),
                )

    return None

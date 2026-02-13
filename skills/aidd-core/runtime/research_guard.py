from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from aidd_runtime import gates
from aidd_runtime import runtime
from aidd_runtime.feature_ids import resolve_aidd_root
from aidd_runtime.rlm_config import detect_lang


class ResearchValidationError(RuntimeError):
    """Raised when researcher validation fails."""


RESEARCH_TEMPLATE_MARKERS = (
    "{{feature}}",
    "{{ticket}}",
    "{{slug}}",
    "{{slug_hint}}",
    "{{date}}",
    "{{owner}}",
    "{{prd_overrides}}",
    "{{paths}}",
    "{{keywords}}",
    "{{paths_discovered}}",
    "{{invalid_paths}}",
    "{{rlm_status}}",
    "{{rlm_pack_path}}",
    "{{rlm_pack_status}}",
    "{{rlm_pack_bytes}}",
    "{{rlm_pack_updated_at}}",
    "{{rlm_warnings}}",
    "{{rlm_nodes_path}}",
    "{{rlm_links_path}}",
)


@dataclass
class ResearchSettings:
    enabled: bool = True
    require_status: list[str] | None = None
    freshness_days: int | None = None
    allow_missing: bool = False
    minimum_paths: int = 0
    allow_pending_baseline: bool = True
    baseline_phrase: str = "контекст пуст"
    branches: list[str] | None = None
    skip_branches: list[str] | None = None
    rlm_enabled: bool = True
    rlm_required_for_langs: list[str] | None = None
    rlm_require_pack: bool = True
    rlm_require_nodes: bool = True
    rlm_require_links: bool = True


@dataclass
class ResearchCheckSummary:
    status: Optional[str]
    path_count: Optional[int] = None
    age_days: Optional[int] = None
    skipped_reason: Optional[str] = None


def _research_cmd_hint(ticket: str) -> str:
    return f"python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/researcher/runtime/research.py --ticket {ticket} --auto"


def _rlm_links_cmd_hint(ticket: str) -> str:
    return f"python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/aidd-rlm/runtime/rlm_links_build.py --ticket {ticket}"


def _rlm_finalize_cmd_hint(ticket: str) -> str:
    return f"python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/aidd-rlm/runtime/rlm_finalize.py --ticket {ticket}"


def _raise_block(reason_code: str, message: str, next_action: str) -> None:
    raise ResearchValidationError(
        f"BLOCK: {message} (reason_code={reason_code}). Next action: `{next_action}`."
    )


def _find_template_markers(doc_text: str) -> list[str]:
    found: list[str] = []
    for marker in RESEARCH_TEMPLATE_MARKERS:
        if marker in doc_text:
            found.append(marker)
    return found


def _normalize_langs(raw: Iterable[str] | None) -> list[str] | None:
    if not raw:
        return None
    items: list[str] = []
    for item in raw:
        if not item:
            continue
        text = str(item).strip().lower()
        if text:
            items.append(text)
    return items or None


def load_settings(root: Path) -> ResearchSettings:
    try:
        config = gates.load_gates_config(root)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ResearchValidationError(str(exc))
    raw = config.get("researcher") or {}
    settings = ResearchSettings()

    if isinstance(raw, dict):
        if "enabled" in raw:
            settings.enabled = bool(raw["enabled"])
        require_status = raw.get("require_status")
        if isinstance(require_status, list):
            settings.require_status = [
                str(item).strip().lower()
                for item in require_status
                if isinstance(item, str) and item.strip()
            ] or None
        if "freshness_days" in raw:
            try:
                settings.freshness_days = int(raw["freshness_days"])
            except (ValueError, TypeError):
                raise ResearchValidationError("config/gates.json: поле researcher.freshness_days должно быть числом")
        if "allow_missing" in raw:
            settings.allow_missing = bool(raw["allow_missing"])
        if "minimum_paths" in raw:
            try:
                settings.minimum_paths = max(int(raw["minimum_paths"]), 0)
            except (ValueError, TypeError):
                raise ResearchValidationError("config/gates.json: поле researcher.minimum_paths должно быть числом")
        if "allow_pending_baseline" in raw:
            settings.allow_pending_baseline = bool(raw["allow_pending_baseline"])
        if "baseline_phrase" in raw and isinstance(raw["baseline_phrase"], str):
            settings.baseline_phrase = raw["baseline_phrase"].strip()
        settings.branches = gates.normalize_patterns(raw.get("branches"))
        settings.skip_branches = gates.normalize_patterns(raw.get("skip_branches"))

    rlm_cfg = config.get("rlm") or {}
    if isinstance(rlm_cfg, dict):
        if "enabled" in rlm_cfg:
            settings.rlm_enabled = bool(rlm_cfg.get("enabled"))
        settings.rlm_required_for_langs = _normalize_langs(rlm_cfg.get("required_for_langs"))
        if "require_pack" in rlm_cfg:
            settings.rlm_require_pack = bool(rlm_cfg.get("require_pack"))
        if "require_nodes" in rlm_cfg:
            settings.rlm_require_nodes = bool(rlm_cfg.get("require_nodes"))
        if "require_links" in rlm_cfg:
            settings.rlm_require_links = bool(rlm_cfg.get("require_links"))

    return settings


def _extract_status(doc_text: str) -> Optional[str]:
    for line in doc_text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("status:"):
            return stripped.split(":", 1)[1].strip().lower()
    return None


def _resolve_report_path(root: Path, raw: Optional[str]) -> Optional[Path]:
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute():
        return path
    parts = path.parts
    if parts and parts[0] == "aidd" and root.name == "aidd":
        path = Path(*parts[1:])
    candidate = (root / path).resolve()
    if candidate.exists():
        return candidate
    if root.name == "aidd":
        workspace_candidate = (root.parent / path).resolve()
        if workspace_candidate.exists():
            return workspace_candidate
    return candidate


def _find_pack_variant(root: Path, name: str) -> Path | None:
    base = root / "reports" / "research"
    candidate = base / f"{name}.pack.json"
    return candidate if candidate.exists() else None


def _load_pack_payload(path: Path) -> Optional[dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _load_stage(root: Path) -> str:
    return runtime.read_active_stage(root)


def _detect_langs_from_files(files: Iterable[str], required_langs: Iterable[str]) -> set[str]:
    wanted = {lang for lang in required_langs if lang}
    if not wanted:
        return set()
    found: set[str] = set()
    for raw in files:
        if not raw:
            continue
        lang = detect_lang(Path(str(raw)))
        if lang and lang in wanted:
            found.add(lang)
    return found


def _detect_langs_from_paths(root: Path, paths: Iterable[str], required_langs: Iterable[str]) -> set[str]:
    exts_by_lang = {
        "kt": {".kt"},
        "kts": {".kts"},
        "java": {".java"},
        "js": {".js", ".jsx"},
        "ts": {".ts", ".tsx"},
        "py": {".py"},
        "go": {".go"},
    }
    wanted = {lang for lang in required_langs if lang in exts_by_lang}
    if not wanted:
        return set()
    found: set[str] = set()
    max_files = 5000
    scanned = 0
    for raw in paths:
        if scanned >= max_files:
            break
        candidate = _resolve_report_path(root, raw)
        if not candidate or not candidate.exists():
            continue
        if candidate.is_file():
            ext = candidate.suffix.lower()
            for lang, exts in exts_by_lang.items():
                if lang in wanted and ext in exts:
                    found.add(lang)
            scanned += 1
            continue
        for base, _, files in os.walk(candidate):
            for name in files:
                scanned += 1
                if scanned >= max_files:
                    break
                ext = Path(name).suffix.lower()
                for lang, exts in exts_by_lang.items():
                    if lang in wanted and ext in exts:
                        found.add(lang)
            if scanned >= max_files:
                break
    return found


def _parse_iso_datetime(value: object) -> Optional[dt.datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        if text.endswith("Z"):
            return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.datetime.fromisoformat(text)
    except ValueError:
        return None


def _count_rlm_nodes(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                node_kind = str(payload.get("node_kind") or "").strip().lower()
                if node_kind and node_kind != "file":
                    continue
                count += 1
    except OSError:
        return 0
    return count


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    count += 1
    except OSError:
        return 0
    return count


def _load_rlm_links_stats(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _should_require_rlm(
    root: Path,
    *,
    settings: ResearchSettings,
    rlm_targets: dict,
) -> bool:
    if not settings.rlm_enabled:
        return False
    required_langs = settings.rlm_required_for_langs or []
    if not required_langs:
        return True

    files = rlm_targets.get("files") or []
    detected = _detect_langs_from_files([str(item) for item in files], required_langs)
    if detected:
        return True

    paths = rlm_targets.get("paths") or []
    paths_discovered = rlm_targets.get("paths_discovered") or []
    if not paths and not paths_discovered:
        paths = ["src"]
    detected = _detect_langs_from_paths(root, list(paths) + list(paths_discovered), required_langs)
    return bool(set(required_langs) & detected)


def _validate_rlm_evidence(
    root: Path,
    ticket: str,
    *,
    settings: ResearchSettings,
    doc_status: Optional[str] = None,
) -> None:
    rlm_targets_path = root / "reports" / "research" / f"{ticket}-rlm-targets.json"
    rlm_manifest_path = root / "reports" / "research" / f"{ticket}-rlm-manifest.json"
    rlm_worklist_path = _find_pack_variant(root, f"{ticket}-rlm.worklist") or (
        root / "reports" / "research" / f"{ticket}-rlm.worklist.pack.json"
    )
    rlm_nodes_path = root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
    rlm_links_path = root / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
    rlm_pack_path = _find_pack_variant(root, f"{ticket}-rlm") or (root / "reports" / "research" / f"{ticket}-rlm.pack.json")
    rlm_links_stats_path = root / "reports" / "research" / f"{ticket}-rlm.links.stats.json"

    if not rlm_targets_path.exists():
        _raise_block(
            "rlm_targets_missing",
            "отсутствует базовый RLM артефакт rlm-targets.json",
            _research_cmd_hint(ticket),
        )
    if not rlm_manifest_path.exists():
        _raise_block(
            "rlm_manifest_missing",
            "отсутствует базовый RLM артефакт rlm-manifest.json",
            _research_cmd_hint(ticket),
        )
    if not rlm_worklist_path.exists():
        _raise_block(
            "rlm_worklist_missing",
            "отсутствует базовый RLM артефакт rlm.worklist.pack",
            _research_cmd_hint(ticket),
        )

    try:
        rlm_targets = json.loads(rlm_targets_path.read_text(encoding="utf-8"))
    except Exception:
        rlm_targets = {}

    if not _should_require_rlm(root, settings=settings, rlm_targets=rlm_targets if isinstance(rlm_targets, dict) else {}):
        return

    worklist_status = None
    worklist_entries = None
    worklist_payload = _load_pack_payload(rlm_worklist_path)
    if isinstance(worklist_payload, dict):
        worklist_status = str(worklist_payload.get("status") or "").strip().lower() or None
        entries = worklist_payload.get("entries")
        if isinstance(entries, list):
            worklist_entries = len(entries)

    stage = _load_stage(root)
    normalized_status = (doc_status or "").strip().lower()
    ready_required = stage in {"plan", "review", "qa"} or normalized_status == "reviewed"

    nodes_exists = rlm_nodes_path.exists()
    nodes_total = _count_rlm_nodes(rlm_nodes_path) if nodes_exists else 0

    links_exists = rlm_links_path.exists()
    links_rows = _count_jsonl_rows(rlm_links_path) if links_exists else 0
    links_total: Optional[int] = None
    links_stats = _load_rlm_links_stats(rlm_links_stats_path)
    if isinstance(links_stats, dict):
        try:
            links_total = int(links_stats.get("links_total") or 0)
        except (TypeError, ValueError):
            links_total = None
    links_empty = (links_total == 0) if links_total is not None else (links_rows == 0)

    pack_exists = rlm_pack_path.exists()
    pack_payload = _load_pack_payload(rlm_pack_path) if pack_exists else None

    rlm_status = None
    if isinstance(pack_payload, dict):
        raw_status = str(pack_payload.get("rlm_status") or pack_payload.get("status") or "").strip().lower()
        if raw_status in {"ready", "pending", "warn", "warning"}:
            rlm_status = "warn" if raw_status == "warning" else raw_status
    if worklist_status is not None:
        if worklist_status == "ready" and (worklist_entries or 0) == 0 and nodes_total > 0 and not links_empty:
            rlm_status = "ready"
        elif rlm_status != "warn":
            rlm_status = "pending"
    if not rlm_status:
        if nodes_total > 0 and not links_empty and pack_exists:
            rlm_status = "ready"
        elif links_empty and (nodes_total > 0 or pack_exists):
            rlm_status = "warn"
        else:
            rlm_status = "pending"

    links_warn = settings.rlm_require_links and links_empty

    if ready_required:
        if settings.rlm_require_nodes and (not nodes_exists or nodes_total == 0):
            _raise_block(
                "rlm_nodes_missing",
                "для текущей стадии нужны RLM nodes (rlm.nodes.jsonl), но они отсутствуют или пусты",
                f"python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/aidd-rlm/runtime/rlm_nodes_build.py --bootstrap --ticket {ticket}",
            )
        if links_warn:
            _raise_block(
                "rlm_links_empty_warn",
                "rlm links empty",
                _rlm_links_cmd_hint(ticket),
            )
        if settings.rlm_require_pack and not pack_exists:
            _raise_block(
                "rlm_pack_missing",
                "для текущей стадии нужен RLM pack, но он отсутствует",
                _rlm_finalize_cmd_hint(ticket),
            )
        if rlm_status != "ready":
            _raise_block(
                "rlm_status_pending",
                "rlm_status=pending — требуется rlm_status=ready с nodes/links/pack для текущей стадии",
                _rlm_finalize_cmd_hint(ticket),
            )
        return

    if rlm_status == "warn":
        print(
            "[aidd] WARN: rlm links empty (reason_code=rlm_links_empty_warn). "
            f"Hint: выполните `{_rlm_links_cmd_hint(ticket)}`.",
            file=sys.stderr,
        )
        return

    if stage in {"research", "implement"}:
        if not nodes_exists or links_empty or not pack_exists:
            print(
                f"[aidd] WARN: rlm_status={rlm_status} for stage={stage}; nodes/links/pack ещё не полностью собраны.",
                file=sys.stderr,
            )
        if worklist_entries:
            threshold = max(1, int(worklist_entries * 0.5))
            if nodes_total < threshold:
                print(
                    "[aidd] WARN: rlm pack partial — "
                    f"nodes_total={nodes_total} worklist_entries={worklist_entries}.",
                    file=sys.stderr,
                )


def validate_research(
    root: Path,
    ticket: str,
    *,
    settings: ResearchSettings,
    branch: Optional[str] = None,
) -> ResearchCheckSummary:
    if not settings.enabled:
        return ResearchCheckSummary(status=None, skipped_reason="disabled")
    if not gates.branch_enabled(branch, allow=settings.branches, skip=settings.skip_branches):
        return ResearchCheckSummary(status=None, skipped_reason="branch-skip")

    doc_path = root / "docs" / "research" / f"{ticket}.md"
    rlm_targets_path = root / "reports" / "research" / f"{ticket}-rlm-targets.json"

    if not doc_path.exists():
        if settings.allow_missing:
            return ResearchCheckSummary(status=None, skipped_reason="missing-allowed")
        _raise_block(
            "research_report_missing",
            f"нет отчёта Researcher для {ticket}",
            _research_cmd_hint(ticket),
        )

    try:
        doc_text = doc_path.read_text(encoding="utf-8")
    except Exception:
        _raise_block(
            "research_report_unreadable",
            f"не удалось прочитать docs/research/{ticket}.md",
            _research_cmd_hint(ticket),
        )
    doc_text_lower = doc_text.lower()
    stale_markers = _find_template_markers(doc_text)
    if stale_markers:
        sample = ", ".join(sorted(stale_markers[:3]))
        _raise_block(
            "research_template_stale",
            f"docs/research/{ticket}.md содержит неразрешённые template markers ({sample})",
            _research_cmd_hint(ticket),
        )

    status = _extract_status(doc_text)
    required_statuses = settings.require_status or ["reviewed"]
    required_statuses = [item for item in required_statuses if item]
    if required_statuses:
        if not status:
            _raise_block(
                "research_status_missing",
                f"docs/research/{ticket}.md не содержит строки `Status:` или она пуста",
                _research_cmd_hint(ticket),
            )
        if status not in required_statuses:
            if status == "pending" and settings.allow_pending_baseline:
                baseline_phrase = settings.baseline_phrase.strip().lower()
                if baseline_phrase and baseline_phrase in doc_text_lower:
                    return ResearchCheckSummary(status=status, skipped_reason="pending-baseline")
                _raise_block(
                    "baseline_missing",
                    "статус Researcher `pending` допустим только для baseline (нужна отметка baseline в отчёте)",
                    _research_cmd_hint(ticket),
                )
            _raise_block(
                "research_status_invalid",
                f"статус Researcher `{status}` не входит в {required_statuses}",
                _research_cmd_hint(ticket),
            )

    path_count: Optional[int] = None
    min_paths = settings.minimum_paths or 0
    targets_payload: dict = {}
    if min_paths > 0 or settings.freshness_days:
        try:
            payload = json.loads(rlm_targets_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            _raise_block(
                "rlm_targets_missing",
                "отсутствует rlm-targets.json",
                _research_cmd_hint(ticket),
            )
        except json.JSONDecodeError:
            _raise_block(
                "rlm_targets_invalid",
                "повреждён rlm-targets.json",
                _research_cmd_hint(ticket),
            )
        targets_payload = payload if isinstance(payload, dict) else {}

    if min_paths > 0:
        paths = targets_payload.get("paths") or []
        path_count = len(paths)
        if path_count < min_paths:
            raise ResearchValidationError(
                f"BLOCK: RLM targets содержат только {path_count} директорий (минимум {min_paths})."
            )

    age_days: Optional[int] = None
    freshness_days = settings.freshness_days
    if freshness_days:
        generated_dt = _parse_iso_datetime(targets_payload.get("generated_at"))
        if generated_dt is None:
            raise ResearchValidationError(
                f"BLOCK: RLM targets ({rlm_targets_path}) не содержат корректное поле generated_at."
            )
        now = dt.datetime.now(dt.timezone.utc)
        age_days = (now - generated_dt.astimezone(dt.timezone.utc)).days
        if age_days > int(freshness_days):
            raise ResearchValidationError(
                f"BLOCK: RLM targets превысили лимит свежести ({age_days} дней) → обновите {_research_cmd_hint(ticket)}."
            )

    _validate_rlm_evidence(
        root,
        ticket,
        settings=settings,
        doc_status=status,
    )

    return ResearchCheckSummary(status=status, path_count=path_count, age_days=age_days)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the Researcher report status for the active feature.",
    )
    parser.add_argument("--ticket", "--slug", dest="ticket", required=True, help="Feature ticket to validate (alias: --slug).")
    parser.add_argument(
        "--branch",
        help="Current Git branch (used to evaluate branch/skip rules in config/gates.json).",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    root = resolve_aidd_root(Path.cwd())
    if not (root / "docs").exists():
        parser.exit(
            1,
            f"BLOCK: expected aidd/docs at {root / 'docs'}. "
            f"Run '/feature-dev-aidd:aidd-init' or 'python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/aidd-init/runtime/init.py' from the workspace root.",
        )
    settings = load_settings(root)
    try:
        summary = validate_research(
            root,
            args.ticket,
            settings=settings,
            branch=args.branch,
        )
    except ResearchValidationError as exc:
        parser.exit(1, f"{exc}\n")
    if summary.status is None:
        if summary.skipped_reason:
            print(f"research gate skipped ({summary.skipped_reason}).")
        else:
            print("research gate disabled — ничего проверять.")
    else:
        details = []
        details.append(f"status: {summary.status}")
        if summary.path_count is not None:
            details.append(f"paths: {summary.path_count}")
        if summary.age_days is not None:
            details.append(f"age: {summary.age_days}d")
        print(f"research gate OK ({', '.join(details)}).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

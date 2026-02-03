from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from tools import gates
from tools.feature_ids import resolve_aidd_root
from tools.rlm_config import detect_lang

class ResearchValidationError(RuntimeError):
    """Raised when researcher validation fails."""


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
    stage_path = root / "docs" / ".active_stage"
    if not stage_path.exists():
        return ""
    return stage_path.read_text(encoding="utf-8", errors="replace").strip().lower()


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


def _resolve_rlm_path(root: Path, context: dict, key: str, fallback: Path) -> Path:
    raw = context.get(key)
    resolved = _resolve_report_path(root, raw) if isinstance(raw, str) and raw else None
    return resolved or fallback


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


def _should_require_rlm(
    root: Path,
    ticket: str,
    *,
    settings: ResearchSettings,
    rlm_targets_path: Path,
    research_targets_path: Path,
) -> bool:
    if not settings.rlm_enabled:
        return False
    required_langs = settings.rlm_required_for_langs or []
    if not required_langs:
        return True
    try:
        targets = json.loads(rlm_targets_path.read_text(encoding="utf-8"))
    except Exception:
        targets = {}
    files = targets.get("files") or []
    detected = _detect_langs_from_files([str(item) for item in files], required_langs)
    if detected:
        return True
    try:
        fallback_targets = json.loads(research_targets_path.read_text(encoding="utf-8"))
    except Exception:
        fallback_targets = {}
    paths = fallback_targets.get("paths") or []
    paths_discovered = fallback_targets.get("paths_discovered") or []
    if not paths and not paths_discovered:
        paths = ["src"]
    detected = _detect_langs_from_paths(root, list(paths) + list(paths_discovered), required_langs)
    return bool(set(required_langs) & detected)


def _validate_rlm_evidence(
    root: Path,
    ticket: str,
    *,
    settings: ResearchSettings,
    context_path: Path,
    targets_path: Path,
    doc_status: Optional[str] = None,
) -> None:
    try:
        context = json.loads(context_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ResearchValidationError(
            f"BLOCK: отсутствует {context_path}; выполните "
            f"${{CLAUDE_PLUGIN_ROOT}}/tools/research.sh --ticket {ticket} --auto."
        )
    except json.JSONDecodeError:
        raise ResearchValidationError(f"BLOCK: повреждён {context_path}; пересоздайте его.")

    rlm_targets_path = _resolve_rlm_path(
        root,
        context,
        "rlm_targets_path",
        root / "reports" / "research" / f"{ticket}-rlm-targets.json",
    )
    if not _should_require_rlm(
        root,
        ticket,
        settings=settings,
        rlm_targets_path=rlm_targets_path,
        research_targets_path=targets_path,
    ):
        return

    rlm_manifest_path = _resolve_rlm_path(
        root,
        context,
        "rlm_manifest_path",
        root / "reports" / "research" / f"{ticket}-rlm-manifest.json",
    )
    rlm_worklist_path = _resolve_rlm_path(
        root,
        context,
        "rlm_worklist_path",
        _find_pack_variant(root, f"{ticket}-rlm.worklist")
        or (root / "reports" / "research" / f"{ticket}-rlm.worklist.pack.json"),
    )
    rlm_nodes_path = _resolve_rlm_path(
        root,
        context,
        "rlm_nodes_path",
        root / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl",
    )
    rlm_links_path = _resolve_rlm_path(
        root,
        context,
        "rlm_links_path",
        root / "reports" / "research" / f"{ticket}-rlm.links.jsonl",
    )
    rlm_pack_path = _resolve_rlm_path(
        root,
        context,
        "rlm_pack_path",
        _find_pack_variant(root, f"{ticket}-rlm") or (root / "reports" / "research" / f"{ticket}-rlm.pack.json"),
    )

    rlm_status = str(context.get("rlm_status") or "pending").strip().lower()
    worklist_status = None
    worklist_entries = None
    if rlm_worklist_path.exists():
        payload = _load_pack_payload(rlm_worklist_path)
        if isinstance(payload, dict):
            worklist_status = str(payload.get("status") or "").strip().lower() or None
            entries = payload.get("entries")
            if isinstance(entries, list):
                worklist_entries = len(entries)
    if worklist_status == "ready" and worklist_entries == 0:
        rlm_status = "ready"
    elif worklist_status:
        rlm_status = "pending"
    stage = _load_stage(root)
    normalized_status = (doc_status or "").strip().lower()
    ready_required = stage in {"plan", "review", "qa"} or normalized_status == "reviewed"

    manifest_total = None
    if rlm_manifest_path.exists():
        try:
            manifest_payload = json.loads(rlm_manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest_payload = None
        if isinstance(manifest_payload, dict):
            files = manifest_payload.get("files")
            if isinstance(files, list):
                manifest_total = len(files)

    nodes_ok = rlm_nodes_path.exists()
    links_ok = rlm_links_path.exists()
    pack_ok = rlm_pack_path.exists()
    nodes_total = _count_rlm_nodes(rlm_nodes_path) if nodes_ok else 0

    if rlm_status == "ready":
        if settings.rlm_require_nodes and not nodes_ok:
            raise ResearchValidationError(
                "BLOCK: rlm_status=ready, но nodes.jsonl отсутствует. "
                f"Hint: выполните agent-flow по worklist или `${{CLAUDE_PLUGIN_ROOT}}/tools/rlm_nodes_build.py --bootstrap --ticket {ticket}`."
            )
        if settings.rlm_require_nodes and (manifest_total or 0) > 0 and nodes_total == 0:
            raise ResearchValidationError(
                "BLOCK: rlm_status=ready, но nodes.jsonl пустой. "
                f"Hint: выполните agent-flow по worklist или `${{CLAUDE_PLUGIN_ROOT}}/tools/rlm_nodes_build.py --bootstrap --ticket {ticket}`."
            )
        if settings.rlm_require_links and not links_ok:
            raise ResearchValidationError(
                "BLOCK: rlm_status=ready, но links.jsonl отсутствует. "
                f"Hint: выполните `${{CLAUDE_PLUGIN_ROOT}}/tools/rlm-links-build.sh --ticket {ticket}`."
            )
        if settings.rlm_require_pack and not pack_ok:
            raise ResearchValidationError(
                "BLOCK: rlm_status=ready, но rlm pack отсутствует. "
                f"Hint: выполните `${{CLAUDE_PLUGIN_ROOT}}/tools/reports_pack.py` для RLM pack."
            )
        return

    if ready_required:
        raise ResearchValidationError(
            "BLOCK: rlm_status=pending — требуется rlm_status=ready "
            "с nodes/links/pack для текущей стадии."
        )

    missing = []
    if not rlm_targets_path.exists():
        missing.append("rlm-targets.json")
    if not rlm_manifest_path.exists():
        missing.append("rlm-manifest.json")
    if not rlm_worklist_path.exists():
        missing.append("rlm.worklist.pack")
    if missing:
        missing_label = ", ".join(missing)
        raise ResearchValidationError(
            f"BLOCK: rlm_status=pending, но отсутствуют {missing_label}. "
            f"Пересоберите research или запустите `${{CLAUDE_PLUGIN_ROOT}}/tools/research.sh --ticket {ticket} --auto`."
        )
    if stage in {"research", "implement"}:
        print(
            f"[aidd] WARN: rlm_status=pending for stage={stage}; "
            "nodes/links/pack ещё не собраны.",
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
    context_path = root / "reports" / "research" / f"{ticket}-context.json"
    targets_path = root / "reports" / "research" / f"{ticket}-targets.json"

    if not doc_path.exists():
        if settings.allow_missing:
            return ResearchCheckSummary(status=None, skipped_reason="missing-allowed")
        raise ResearchValidationError(
            f"BLOCK: нет отчёта Researcher для {ticket} → запустите "
            f"`${{CLAUDE_PLUGIN_ROOT}}/tools/research.sh --ticket {ticket} --auto` "
            f"и оформите docs/research/{ticket}.md"
        )

    try:
        doc_text = doc_path.read_text(encoding="utf-8")
    except Exception:
        raise ResearchValidationError(f"BLOCK: не удалось прочитать docs/research/{ticket}.md.")
    doc_text_lower = doc_text.lower()

    status = _extract_status(doc_text)
    required_statuses = settings.require_status or ["reviewed"]
    required_statuses = [item for item in required_statuses if item]
    if required_statuses:
        if not status:
            raise ResearchValidationError(f"BLOCK: docs/research/{ticket}.md не содержит строки `Status:` или она пуста.")
        if status not in required_statuses:
            if status == "pending" and settings.allow_pending_baseline:
                baseline_phrase = settings.baseline_phrase.strip().lower()
                if baseline_phrase and baseline_phrase in doc_text_lower:
                    try:
                        context = json.loads(context_path.read_text(encoding="utf-8"))
                    except FileNotFoundError:
                        raise ResearchValidationError(
                            f"BLOCK: отсутствует {context_path}; выполните "
                            f"${{CLAUDE_PLUGIN_ROOT}}/tools/research.sh --ticket {ticket} --auto."
                        )
                    except json.JSONDecodeError:
                        raise ResearchValidationError(f"BLOCK: повреждён {context_path}; пересоздайте его.")
                    profile = context.get("profile") or {}
                    if bool(profile.get("is_new_project")) and bool(context.get("auto_mode")):
                        return ResearchCheckSummary(status=status, skipped_reason="pending-baseline")
                raise ResearchValidationError(
                    "BLOCK: статус Researcher `pending` допустим только для baseline (нужна отметка и auto_mode для нового проекта)."
                )
            raise ResearchValidationError(
                f"BLOCK: статус Researcher `{status}` не входит в {required_statuses} → актуализируйте отчёт."
            )

    path_count: Optional[int] = None
    min_paths = settings.minimum_paths or 0
    if min_paths > 0:
        try:
            targets = json.loads(targets_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ResearchValidationError(f"BLOCK: отсутствует {targets_path} с целевыми директориями Researcher.")
        except json.JSONDecodeError:
            raise ResearchValidationError(
                f"BLOCK: повреждён файл {targets_path}; пересоберите его командой "
                f"${{CLAUDE_PLUGIN_ROOT}}/tools/research.sh --ticket {ticket} --auto."
            )
        paths = targets.get("paths") or []
        path_count = len(paths)
        if path_count < min_paths:
            raise ResearchValidationError(
                f"BLOCK: Researcher targets содержат только {path_count} директорий (минимум {min_paths})."
            )

    age_days: Optional[int] = None
    freshness_days = settings.freshness_days
    if freshness_days:
        try:
            context = json.loads(context_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ResearchValidationError(
                f"BLOCK: отсутствует {context_path}; выполните "
                f"${{CLAUDE_PLUGIN_ROOT}}/tools/research.sh --ticket {ticket} --auto."
            )
        except json.JSONDecodeError:
            raise ResearchValidationError(f"BLOCK: повреждён {context_path}; пересоздайте его.")
        generated_raw = context.get("generated_at")
        if not isinstance(generated_raw, str) or not generated_raw:
            raise ResearchValidationError(
                f"BLOCK: контекст Researcher ({context_path}) не содержит поля generated_at."
            )
        try:
            if generated_raw.endswith("Z"):
                generated_dt = dt.datetime.fromisoformat(generated_raw.replace("Z", "+00:00"))
            else:
                generated_dt = dt.datetime.fromisoformat(generated_raw)
        except ValueError:
            raise ResearchValidationError(
                f"BLOCK: некорректная метка времени generated_at в {context_path}."
            )
        now = dt.datetime.now(dt.timezone.utc)
        age_days = (now - generated_dt.astimezone(dt.timezone.utc)).days
        if age_days > int(freshness_days):
            raise ResearchValidationError(
                f"BLOCK: контекст Researcher устарел ({age_days} дней) → обновите "
                f"${{CLAUDE_PLUGIN_ROOT}}/tools/research.sh --ticket {ticket} --auto."
            )

    _validate_rlm_evidence(
        root,
        ticket,
        settings=settings,
        context_path=context_path,
        targets_path=targets_path,
        doc_status=status,
    )

    return ResearchCheckSummary(status=status, path_count=path_count, age_days=age_days)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the Researcher report status for the active feature.",
    )
    parser.add_argument("--ticket", "--slug", dest="ticket", required=True, help="Feature ticket to validate (legacy alias: --slug).")
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
            f"Run '/feature-dev-aidd:aidd-init' or '${{CLAUDE_PLUGIN_ROOT}}/tools/init.sh' from the workspace root.",
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

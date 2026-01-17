from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, Optional

from tools.feature_ids import resolve_project_root

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


@dataclass
class ResearchCheckSummary:
    status: Optional[str]
    path_count: Optional[int] = None
    age_days: Optional[int] = None
    skipped_reason: Optional[str] = None


def _load_gates_config(root: Path) -> dict:
    config_path = root / "config" / "gates.json"
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        raise ResearchValidationError(f"не удалось прочитать {config_path}: {exc}")


def _normalize_patterns(raw: Iterable[str] | None) -> list[str] | None:
    if not raw:
        return None
    patterns: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            patterns.append(item.strip())
    return patterns or None


def load_settings(root: Path) -> ResearchSettings:
    config = _load_gates_config(root)
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
        settings.branches = _normalize_patterns(raw.get("branches"))
        settings.skip_branches = _normalize_patterns(raw.get("skip_branches"))

    return settings


def _branch_enabled(branch: Optional[str], settings: ResearchSettings) -> bool:
    if not branch:
        return True
    if settings.skip_branches and any(fnmatch(branch, pattern) for pattern in settings.skip_branches):
        return False
    if settings.branches and not any(fnmatch(branch, pattern) for pattern in settings.branches):
        return False
    return True


def _extract_status(doc_text: str) -> Optional[str]:
    for line in doc_text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("status:"):
            return stripped.split(":", 1)[1].strip().lower()
    return None


def validate_research(
    root: Path,
    ticket: str,
    *,
    settings: ResearchSettings,
    branch: Optional[str] = None,
) -> ResearchCheckSummary:
    if not settings.enabled:
        return ResearchCheckSummary(status=None, skipped_reason="disabled")
    if not _branch_enabled(branch, settings):
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
    root = resolve_project_root(Path.cwd())
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

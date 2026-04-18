from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _detect_plugin_root() -> Path:
    env_root = (os.getenv("CLAUDE_PLUGIN_ROOT") or "").strip()
    if env_root:
        candidate = Path(env_root).expanduser().resolve()
        if (candidate / "aidd_runtime").is_dir():
            return candidate

    probe = Path(__file__).resolve()
    for parent in (probe.parent, *probe.parents):
        if (parent / "aidd_runtime").is_dir():
            return parent
    return probe.parent


_PLUGIN_ROOT = _detect_plugin_root()
os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(_PLUGIN_ROOT))
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from aidd_runtime import runtime


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show summary for a ticket (index + recent events).",
    )
    parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Rebuild index before showing status.",
    )
    parser.add_argument(
        "--events",
        type=int,
        default=5,
        help="Number of recent events to show (default: 5).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        _, target = runtime.resolve_roots()
    except RuntimeError as exc:
        print(f"[status] unavailable: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print("[status] unavailable")
        print(f"- Reason: {exc}")
        print("- Next action: /feature-dev-aidd:aidd-init")
        print("- Status mode: read-only (no workspace mutations performed)")
        return 0

    if not (target / "docs").exists():
        print("[status] unavailable")
        print(
            f"- Reason: workflow files not found at {runtime.rel_path(target / 'docs', target)}"
        )
        print("- Next action: /feature-dev-aidd:aidd-init")
        print("- Status mode: read-only (no workspace mutations performed)")
        return 0

    try:
        ticket, context = runtime.require_ticket(
            target,
            ticket=getattr(args, "ticket", None),
            slug_hint=getattr(args, "slug_hint", None),
        )
    except (ValueError, RuntimeError) as exc:
        print(f"[status] unavailable: {exc}", file=sys.stderr)
        return 1
    slug = context.slug_hint or ticket

    from aidd_runtime.reports import events as _events
    from aidd_runtime.reports import tests_log as _tests_log

    index_path = target / "docs" / "index" / f"{ticket}.json"
    if args.refresh:
        from aidd_runtime import index_sync as _index_sync

        _index_sync.write_index(target, ticket, slug)
    elif not index_path.exists():
        rel_index = runtime.rel_path(index_path, target)
        print(f"[status] {ticket}")
        print(f"- Index snapshot missing: {rel_index}")
        print(
            f"- Next action: python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/status/runtime/status.py --ticket {ticket} --refresh"
        )
        print("- Status mode: read-only (no workspace mutations performed)")
        return 0

    try:
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(
            f"[status] unavailable: failed to read {runtime.rel_path(index_path, target)} ({exc})",
            file=sys.stderr,
        )
        print(
            f"[status] next action: python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/status/runtime/status.py --ticket {ticket} --refresh",
            file=sys.stderr,
        )
        return 1

    stage = index_payload.get("stage") or ""
    summary = index_payload.get("summary") or ""
    print(f"[status] {ticket}" + (f" (stage: {stage})" if stage else ""))
    if summary:
        print(f"- Summary: {summary}")
    updated = index_payload.get("updated")
    if updated:
        print(f"- Updated: {updated}")
    artifacts = index_payload.get("artifacts") or []
    if artifacts:
        print("- Artifacts:")
        for item in artifacts:
            print(f"  - {item}")
    reports = index_payload.get("reports") or []
    if reports:
        print("- Reports (actual):")
        for item in reports:
            print(f"  - {item}")
    doc_statuses = index_payload.get("doc_statuses") or {}
    if isinstance(doc_statuses, dict) and doc_statuses:
        print("- Document statuses:")
        for key, value in doc_statuses.items():
            print(f"  - {key}: {value}")
    expected_reports = index_payload.get("expected_reports") or []
    if expected_reports:
        print("- Expected reports (planned):")
        for item in expected_reports:
            print(f"  - {item}")
    missing_expected_reports = index_payload.get("missing_expected_reports") or []
    if missing_expected_reports:
        print("- Missing expected reports:")
        for item in missing_expected_reports:
            print(f"  - {item}")
    next3 = index_payload.get("next3") or []
    if next3:
        print("- AIDD:NEXT_3:")
        for item in next3:
            print(f"  - {item}")
    open_questions = index_payload.get("open_questions") or []
    if open_questions:
        print("- Open questions:")
        for item in open_questions:
            print(f"  - {item}")
    risks = index_payload.get("risks_top5") or []
    if risks:
        print("- Risks:")
        for item in risks:
            print(f"  - {item}")
    checks = index_payload.get("checks") or []
    if checks:
        print("- Checks:")
        for item in checks:
            name = item.get("name") if isinstance(item, dict) else None
            status = item.get("status") if isinstance(item, dict) else None
            path = item.get("path") if isinstance(item, dict) else None
            label = f"{name}: {status}" if name else str(item)
            if path:
                label += f" ({path})"
            print(f"  - {label}")
    truth_checks = index_payload.get("truth_checks") or []
    if truth_checks:
        print("- Truth checks:")
        for item in truth_checks:
            if not isinstance(item, dict):
                print(f"  - {item}")
                continue
            summary_text = item.get("summary") or item.get("code") or "truth-check"
            severity = str(item.get("severity") or "").strip().lower()
            label = f"[{severity}] {summary_text}" if severity else str(summary_text)
            print(f"  - {label}")

    events = index_payload.get("events") or _events.read_events(target, ticket, limit=args.events)
    if events:
        print("- Events:")
        for entry in events:
            repeat_count = int(entry.get("repeat_count") or 1)
            if repeat_count > 1 and entry.get("first_seen") and entry.get("last_seen"):
                line = f"{entry.get('first_seen')}..{entry.get('last_seen')} [{entry.get('type')}]"
            else:
                line = f"{entry.get('ts')} [{entry.get('type')}]"
            status = entry.get("status")
            if status:
                line += f" {status}"
            if repeat_count > 1:
                line += f" x{repeat_count}"
            details = entry.get("details")
            sample_reason = entry.get("sample_reason")
            if sample_reason:
                line += f" — {sample_reason}"
            elif isinstance(details, dict) and details.get("summary"):
                line += f" — {details.get('summary')}"
            print(f"  - {line}")
    test_events = _tests_log.read_log(target, ticket, limit=args.events)
    if test_events:
        print("- Tests log:")
        for entry in test_events:
            timestamp = entry.get("updated_at") or entry.get("ts") or ""
            stage = entry.get("stage") or ""
            scope_key = entry.get("scope_key") or ""
            label = entry.get("status") or entry.get("result") or ""
            line = f"{timestamp} [{label}]"
            if stage:
                line += f" stage={stage}"
            if scope_key:
                line += f" scope={scope_key}"
            details = entry.get("details")
            if isinstance(details, dict) and details.get("summary"):
                line += f" — {details.get('summary')}"
            print(f"  - {line}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

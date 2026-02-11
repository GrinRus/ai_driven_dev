from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Sequence

from aidd_runtime import runtime

DEFAULT_REVIEWER_MARKER = "aidd/reports/reviewer/{ticket}/{scope_key}.tests.json"
DEFAULT_REVIEWER_FIELD = "tests"
DEFAULT_REVIEWER_REQUIRED = ("required",)
DEFAULT_REVIEWER_OPTIONAL = ("optional", "skipped", "not-required")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update reviewer test requirement marker for the active feature.",
    )
    parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to use (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override for marker metadata.",
    )
    parser.add_argument(
        "--status",
        default="required",
        help="Tests state to store in the marker (default: required).",
    )
    parser.add_argument(
        "--scope-key",
        help="Optional scope key override (defaults to active work item).",
    )
    parser.add_argument(
        "--work-item-key",
        help="Optional work item key override (iteration_id=... / id=...).",
    )
    parser.add_argument(
        "--note",
        help="Optional note stored alongside the reviewer marker.",
    )
    parser.add_argument(
        "--requested-by",
        help="Override requested_by field in the marker (defaults to $USER).",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Remove the marker instead of updating it.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()

    ticket, context = runtime.require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )

    reviewer_cfg = runtime.reviewer_gate_config(target)
    marker_template = str(
        reviewer_cfg.get("marker")
        or reviewer_cfg.get("tests_marker")
        or DEFAULT_REVIEWER_MARKER
    )
    work_item_key = (args.work_item_key or runtime.read_active_work_item(target)).strip()
    scope_key = (args.scope_key or runtime.resolve_scope_key(work_item_key, ticket)).strip()
    marker_path = runtime.reviewer_marker_path(
        target,
        marker_template,
        ticket,
        context.slug_hint,
        scope_key=scope_key,
    )
    rel_marker = marker_path.relative_to(target).as_posix()
    fallback_markers: list[Path] = [runtime.resolve_path_for_target(Path(f"aidd/reports/reviewer/{ticket}.json"), target)]
    if marker_path.name.endswith(".tests.json"):
        fallback_markers.append(marker_path.with_name(marker_path.name.replace(".tests.json", ".json")))
    deduped_fallback = [item for item in dict.fromkeys(fallback_markers) if item != marker_path]

    if args.clear:
        if marker_path.exists():
            marker_path.unlink()
            print(f"[aidd] reviewer marker cleared ({rel_marker}).")
        else:
            print(f"[aidd] reviewer marker not found at {rel_marker}.")
        for fallback_path in deduped_fallback:
            if fallback_path.exists():
                try:
                    fallback_path.unlink()
                except OSError:
                    pass
        runtime.maybe_sync_index(target, ticket, context.slug_hint, reason="reviewer-tests")
        return 0

    status = (args.status or "required").strip().lower()
    alias_map = {"skip": "skipped"}
    status = alias_map.get(status, status)

    def _extract_values(primary_key: str, fallback: Sequence[str]) -> list[str]:
        raw = reviewer_cfg.get(primary_key)
        if raw is None:
            source = fallback
        elif isinstance(raw, list):
            source = raw
        else:
            source = [raw]
        values = [str(value).strip().lower() for value in source if str(value).strip()]
        return values or list(fallback)

    required_values = _extract_values("required_values", DEFAULT_REVIEWER_REQUIRED)
    optional_values = _extract_values("optional_values", DEFAULT_REVIEWER_OPTIONAL)
    allowed_values = {*required_values, *optional_values}
    if status not in allowed_values:
        choices = ", ".join(sorted(allowed_values))
        raise ValueError(f"status must be one of: {choices}")

    field_name = str(
        reviewer_cfg.get("tests_field")
        or reviewer_cfg.get("field")
        or DEFAULT_REVIEWER_FIELD
    )

    requested_by = args.requested_by or os.getenv("GIT_AUTHOR_NAME") or os.getenv("USER") or ""
    record: dict = {}
    if marker_path.exists():
        try:
            record = json.loads(marker_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            record = {}

    record.update(
        {
            "ticket": ticket,
            "slug": context.slug_hint or ticket,
            field_name: status,
            "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
    )
    if requested_by:
        record["requested_by"] = requested_by
    if args.note:
        record["note"] = args.note
    elif "note" in record and not record["note"]:
        record.pop("note", None)

    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    for fallback_path in deduped_fallback:
        if not fallback_path.exists():
            continue
        try:
            fallback_path.unlink()
        except OSError:
            pass

    state_label = "required" if status in required_values else status
    print(f"[aidd] reviewer marker updated ({rel_marker} → {state_label}).")
    if status in required_values:
        print("[aidd] format-and-test will trigger test tasks after the next write/edit.")
    runtime.maybe_sync_index(target, ticket, context.slug_hint, reason="reviewer-tests")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

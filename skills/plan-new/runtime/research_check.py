from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(_PLUGIN_ROOT))
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from aidd_runtime import runtime
from aidd_runtime.research_guard import ResearchValidationError, load_settings, validate_research


def _enforce_minimum_rlm_artifacts(target: Path, ticket: str) -> None:
    required = [
        target / "reports" / "research" / f"{ticket}-rlm-targets.json",
        target / "reports" / "research" / f"{ticket}-rlm-manifest.json",
        target / "reports" / "research" / f"{ticket}-rlm.worklist.pack.json",
    ]
    missing = [runtime.rel_path(path, target) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(
            "BLOCK: missing mandatory RLM artifacts for plan gate "
            f"(reason_code=research_artifacts_missing): {', '.join(missing)}"
        )
    for path in required:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(
                "BLOCK: invalid RLM artifact JSON "
                f"(reason_code=research_artifacts_invalid): {runtime.rel_path(path, target)} ({exc})"
            ) from exc
        if not isinstance(payload, dict):
            raise RuntimeError(
                "BLOCK: invalid RLM artifact payload "
                f"(reason_code=research_artifacts_invalid): {runtime.rel_path(path, target)} (expected object)"
            )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the Researcher report status for the active feature.",
    )
    parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to validate (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override for messaging (defaults to docs/.active.json if present).",
    )
    parser.add_argument(
        "--branch",
        help="Current Git branch used to evaluate config.gates researcher branch rules.",
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
    settings = load_settings(target)
    try:
        summary = validate_research(
            target,
            ticket,
            settings=settings,
            branch=args.branch,
        )
    except ResearchValidationError as exc:
        raise RuntimeError(str(exc)) from exc

    if summary.status is None:
        if summary.skipped_reason:
            print(f"[aidd] research gate skipped ({summary.skipped_reason}).")
        else:
            print("[aidd] research gate disabled; nothing to validate.")
        return 0

    _enforce_minimum_rlm_artifacts(target, ticket)

    label = runtime.format_ticket_label(context, fallback=ticket)
    details = [f"status: {summary.status}"]
    if summary.path_count is not None:
        details.append(f"paths: {summary.path_count}")
    if summary.age_days is not None:
        details.append(f"age: {summary.age_days}d")
    print(f"[aidd] research gate OK for `{label}` ({', '.join(details)}).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

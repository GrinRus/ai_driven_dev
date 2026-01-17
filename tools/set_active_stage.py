from __future__ import annotations

import argparse
from pathlib import Path

from tools import runtime
from tools.feature_ids import resolve_project_root as resolve_aidd_root


VALID_STAGES = {
    "idea",
    "research",
    "plan",
    "review-plan",
    "review-prd",
    "spec-interview",
    "tasklist",
    "implement",
    "review",
    "qa",
}


def _normalize_stage(value: str) -> str:
    return value.strip().lower().replace(" ", "-")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Persist the active workflow stage in docs/.active_stage.",
    )
    parser.add_argument("stage", help="Stage name to persist.")
    parser.add_argument(
        "--allow-custom",
        action="store_true",
        help="Allow arbitrary stage values (skip validation).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = resolve_aidd_root(Path.cwd())
    stage = _normalize_stage(args.stage)
    if not args.allow_custom and stage not in VALID_STAGES:
        valid = ", ".join(sorted(VALID_STAGES))
        print(f"[stage] invalid stage '{stage}'. Allowed: {valid}.")
        return 2
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    stage_path = docs_dir / ".active_stage"
    stage_path.write_text(stage + "\n", encoding="utf-8")
    print(f"active stage: {stage}")
    context = runtime.resolve_feature_context(root)
    runtime.maybe_sync_index(root, context.resolved_ticket, context.slug_hint, reason="set-active-stage")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

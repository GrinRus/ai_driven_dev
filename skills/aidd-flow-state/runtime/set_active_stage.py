from __future__ import annotations

import argparse
from pathlib import Path

from aidd_runtime import runtime, stage_lexicon
from aidd_runtime.feature_ids import resolve_aidd_root, write_active_state


VALID_STAGES = set(stage_lexicon.CANONICAL_STAGES)
STAGE_ALIASES = dict(stage_lexicon.STAGE_ALIASES)


def _normalize_stage(value: str) -> str:
    return stage_lexicon.resolve_stage_name(value)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Persist the active workflow stage in docs/.active.json.",
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
    if not args.allow_custom and not stage_lexicon.is_known_stage(args.stage, include_aliases=True):
        valid = ", ".join(stage_lexicon.supported_stage_values(include_aliases=True))
        print(f"[stage] invalid stage '{stage}'. Allowed: {valid}.")
        return 2
    write_active_state(root, stage=stage)
    print(f"active stage: {stage}")
    context = runtime.resolve_feature_context(root)
    runtime.maybe_sync_index(root, context.resolved_ticket, context.slug_hint, reason="set-active-stage")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

from __future__ import annotations

try:
    from aidd_runtime._bootstrap import ensure_repo_root
except ImportError:  # pragma: no cover - direct script execution
    from _bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from aidd_runtime import stage_actions_run  # noqa: E402

DEFAULT_STAGE = "implement"
DESCRIPTION = "Validate implement actions payload with the Python-only stage run contract."


def parse_args(argv: list[str] | None = None):
    return stage_actions_run.parse_args(
        argv,
        default_stage=DEFAULT_STAGE,
        description=DESCRIPTION,
    )


def main(argv: list[str] | None = None) -> int:
    return stage_actions_run.main(
        argv,
        default_stage=DEFAULT_STAGE,
        description=DESCRIPTION,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

from __future__ import annotations

from aidd_runtime import stage_actions_run


def parse_args(
    argv: list[str] | None = None,
    *,
    default_stage: str,
    description: str,
):
    return stage_actions_run.parse_args(
        argv,
        default_stage=default_stage,
        description=description,
    )


def main(
    argv: list[str] | None = None,
    *,
    default_stage: str,
    description: str,
) -> int:
    return stage_actions_run.main(
        argv,
        default_stage=default_stage,
        description=description,
    )

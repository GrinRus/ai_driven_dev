from __future__ import annotations

import runpy

from pathlib import Path

_PLUGIN_ROOT = runpy.run_path(
    next(
        parent / "aidd_runtime" / "plugin_bootstrap.py"
        for parent in Path(__file__).resolve().parents
        if (parent / "aidd_runtime" / "plugin_bootstrap.py").is_file()
    )
)["ensure_plugin_root_on_path"](__file__)

from aidd_runtime import stage_actions_entrypoint

DEFAULT_STAGE = "implement"
DESCRIPTION = "Validate implement actions payload with the Python-only stage run contract."


def parse_args(argv: list[str] | None = None):
    return stage_actions_entrypoint.parse_args(
        argv,
        default_stage=DEFAULT_STAGE,
        description=DESCRIPTION,
    )


def main(argv: list[str] | None = None) -> int:
    return stage_actions_entrypoint.main(
        argv,
        default_stage=DEFAULT_STAGE,
        description=DESCRIPTION,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

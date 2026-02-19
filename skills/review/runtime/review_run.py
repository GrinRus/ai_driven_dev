from __future__ import annotations

import os
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(_PLUGIN_ROOT))
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from aidd_runtime import stage_actions_run

DEFAULT_STAGE = "review"
DESCRIPTION = "Validate review actions payload with the Python-only stage run contract."


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

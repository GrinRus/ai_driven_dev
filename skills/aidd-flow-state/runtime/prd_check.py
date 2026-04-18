from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidd_runtime.entrypoint import bootstrap_wrapper

main = bootstrap_wrapper("aidd_runtime.prd_check", globals())

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_CONTRACTS = REPO_ROOT / "tests" / "repo_tools" / "e2e_prompt" / "prompt_contracts.json"


def read_text(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f"missing contract file: {path}")
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_prompt_contracts() -> Mapping[str, Any]:
    return json.loads(PROMPT_CONTRACTS.read_text(encoding="utf-8"))


def assert_prompt_contract(testcase: Any, *, text: str, contract: Mapping[str, Any], label: str) -> None:
    for needle in contract.get("contains", []):
        testcase.assertIn(needle, text, msg=f"{label}: missing required marker `{needle}`")
    for needle in contract.get("absent", []):
        testcase.assertNotIn(needle, text, msg=f"{label}: forbidden marker `{needle}` present")
    for pattern in contract.get("regex_contains", []):
        if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL) is None:
            testcase.fail(f"{label}: missing regex marker `{pattern}`")
    for pattern in contract.get("regex_absent", []):
        if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            testcase.fail(f"{label}: forbidden regex marker `{pattern}` present")

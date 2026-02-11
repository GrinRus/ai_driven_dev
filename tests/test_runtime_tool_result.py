import sys

from tests.helpers import REPO_ROOT

if str(REPO_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(REPO_ROOT))

from aidd_runtime import runtime  # noqa: E402


def test_resolve_tool_result_id_prefers_id() -> None:
    payload = {"id": "tool-1", "request_id": "req-1"}
    key, warn = runtime.resolve_tool_result_id(payload)
    assert key == "tool-1"
    assert warn == ""


def test_resolve_tool_result_id_falls_back_to_request_id() -> None:
    payload = {"request_id": "req-2"}
    key, warn = runtime.resolve_tool_result_id(payload)
    assert key == "tool_result:req-2"
    assert warn == "tool_result_missing_id request_id=req-2"


def test_resolve_tool_result_id_falls_back_to_index() -> None:
    payload = {}
    key, warn = runtime.resolve_tool_result_id(payload, index=3)
    assert key == "tool_result:3"
    assert warn == "tool_result_missing_id request_id=n/a"

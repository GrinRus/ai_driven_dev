import json

from aidd_runtime.tools import json_patch


def test_json_patch_round_trip():
    old = {"a": 1, "b": {"c": 2}, "list": [1, 2], "remove": "x"}
    new = {"a": 1, "b": {"c": 3}, "list": [1, 2, 3], "added": "y"}

    ops = json_patch.diff(old, new)
    # Apply to a deep copy to avoid in-place mutation surprises.
    result = json_patch.apply(json.loads(json.dumps(old)), ops)

    assert result == new

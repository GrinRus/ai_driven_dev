"""Minimal RFC6902-style JSON patch helpers (add/remove/replace)."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


def _escape_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _unescape_token(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _join_path(parent: str, token: str) -> str:
    escaped = _escape_token(token)
    if parent == "":
        return f"/{escaped}"
    return f"{parent}/{escaped}"


def _parse_pointer(pointer: str) -> List[str]:
    if pointer == "":
        return []
    if not pointer.startswith("/"):
        raise ValueError(f"invalid JSON pointer: {pointer}")
    return [_unescape_token(part) for part in pointer.lstrip("/").split("/")]


def _parse_index(token: str, *, allow_end: bool) -> int:
    if token == "-" and allow_end:
        return -1
    try:
        return int(token)
    except ValueError as exc:
        raise ValueError(f"invalid list index: {token}") from exc


def _resolve_parent(doc: Any, parts: List[str]) -> tuple[Any, str]:
    if not parts:
        raise ValueError("cannot resolve parent for root pointer")
    current = doc
    for token in parts[:-1]:
        if isinstance(current, list):
            index = _parse_index(token, allow_end=False)
            current = current[index]
        elif isinstance(current, dict):
            current = current[token]
        else:
            raise ValueError(f"cannot traverse JSON pointer at {token}")
    return current, parts[-1]


def diff(before: Any, after: Any, path: str = "") -> List[Dict[str, Any]]:
    if type(before) is not type(after):
        return [{"op": "replace", "path": path, "value": after}]
    if isinstance(before, dict):
        ops: List[Dict[str, Any]] = []
        before_keys = set(before)
        after_keys = set(after)
        for key in sorted(before_keys - after_keys):
            ops.append({"op": "remove", "path": _join_path(path, key)})
        for key in sorted(after_keys - before_keys):
            ops.append({"op": "add", "path": _join_path(path, key), "value": after[key]})
        for key in sorted(before_keys & after_keys):
            ops.extend(diff(before[key], after[key], _join_path(path, key)))
        return ops
    if isinstance(before, list):
        if before == after:
            return []
        return [{"op": "replace", "path": path, "value": after}]
    if before != after:
        return [{"op": "replace", "path": path, "value": after}]
    return []


def apply(doc: Any, patch_ops: Iterable[Dict[str, Any]]) -> Any:
    result = doc
    for op in patch_ops:
        result = _apply_op(result, op)
    return result


def _apply_op(doc: Any, op: Dict[str, Any]) -> Any:
    op_type = op.get("op")
    path = op.get("path", "")
    value = op.get("value")

    if path == "":
        if op_type in {"add", "replace"}:
            return value
        raise ValueError("remove at document root is not supported")

    parts = _parse_pointer(path)
    parent, token = _resolve_parent(doc, parts)

    if isinstance(parent, list):
        index = _parse_index(token, allow_end=(op_type == "add"))
        if op_type == "add":
            if index == -1 or index >= len(parent):
                parent.append(value)
            else:
                parent.insert(index, value)
        elif op_type == "replace":
            parent[index] = value
        elif op_type == "remove":
            del parent[index]
        else:
            raise ValueError(f"unsupported op: {op_type}")
        return doc

    if isinstance(parent, dict):
        if op_type == "add":
            parent[token] = value
        elif op_type == "replace":
            parent[token] = value
        elif op_type == "remove":
            parent.pop(token, None)
        else:
            raise ValueError(f"unsupported op: {op_type}")
        return doc

    raise ValueError("unsupported target type for patch op")

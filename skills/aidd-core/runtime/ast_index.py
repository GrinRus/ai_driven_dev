from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from aidd_runtime import runtime
from aidd_runtime.rlm_config import load_conventions


REASON_BINARY_MISSING = "ast_index_binary_missing"
REASON_INDEX_MISSING = "ast_index_index_missing"
REASON_TIMEOUT = "ast_index_timeout"
REASON_JSON_INVALID = "ast_index_json_invalid"
REASON_FALLBACK_RG = "ast_index_fallback_rg"


@dataclass(frozen=True)
class AstIndexConfig:
    mode: str = "auto"
    required: bool = False
    binary: str = "ast-index"
    timeout_s: int = 8
    auto_ensure_index: bool = True
    fallback: str = "rg"
    max_results: int = 200
    allow_fallback_rg: bool = True
    warn_on_fallback: bool = True


@dataclass
class AstIndexResult:
    ok: bool
    reason_code: str = ""
    fallback_reason_code: str = ""
    command: List[str] | None = None
    normalized: List[Dict[str, Any]] | None = None
    payload: Any = None
    stdout: str = ""
    stderr: str = ""
    binary_path: str = ""
    index_ready: bool = False
    version: str = ""


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _as_int(value: Any, *, default: int, minimum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def load_ast_index_config(project_root: Path) -> AstIndexConfig:
    conventions = load_conventions(project_root)
    conv_cfg = conventions.get("ast_index") if isinstance(conventions.get("ast_index"), dict) else {}
    gates_cfg = runtime.load_gates_config(project_root).get("ast_index")
    gate_cfg = gates_cfg if isinstance(gates_cfg, dict) else {}

    mode = str(gate_cfg.get("mode") or conv_cfg.get("mode") or "auto").strip().lower()
    if mode not in {"off", "auto", "required"}:
        mode = "auto"
    required = _as_bool(gate_cfg.get("required"), default=_as_bool(conv_cfg.get("required"), default=False))
    if mode == "required":
        required = True
    if mode == "off":
        required = False

    binary = str(conv_cfg.get("binary") or "ast-index").strip() or "ast-index"
    timeout_s = _as_int(conv_cfg.get("timeout_s"), default=8, minimum=1)
    auto_ensure = _as_bool(conv_cfg.get("auto_ensure_index"), default=True)
    fallback = str(conv_cfg.get("fallback") or "rg").strip().lower() or "rg"
    max_results = _as_int(conv_cfg.get("max_results"), default=200, minimum=1)
    allow_fallback_rg = _as_bool(gate_cfg.get("allow_fallback_rg"), default=True)
    warn_on_fallback = _as_bool(gate_cfg.get("warn_on_fallback"), default=True)

    return AstIndexConfig(
        mode=mode,
        required=required,
        binary=binary,
        timeout_s=timeout_s,
        auto_ensure_index=auto_ensure,
        fallback=fallback,
        max_results=max_results,
        allow_fallback_rg=allow_fallback_rg,
        warn_on_fallback=warn_on_fallback,
    )


def _fallback_reason(config: AstIndexConfig, reason_code: str) -> str:
    if config.allow_fallback_rg and config.fallback == "rg" and reason_code:
        return REASON_FALLBACK_RG
    return ""


def detect(config: AstIndexConfig) -> AstIndexResult:
    if config.mode == "off":
        return AstIndexResult(ok=False, reason_code="", fallback_reason_code="")
    binary_path = shutil.which(config.binary) or ""
    if not binary_path:
        reason_code = REASON_BINARY_MISSING
        return AstIndexResult(
            ok=False,
            reason_code=reason_code,
            fallback_reason_code=_fallback_reason(config, reason_code),
        )
    return AstIndexResult(ok=True, binary_path=binary_path)


def _run_command(command: Sequence[str], *, cwd: Path, timeout_s: int) -> AstIndexResult:
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            check=False,
            text=True,
            capture_output=True,
            timeout=max(1, timeout_s),
        )
    except subprocess.TimeoutExpired as exc:
        return AstIndexResult(
            ok=False,
            reason_code=REASON_TIMEOUT,
            stdout=str(exc.stdout or ""),
            stderr=str(exc.stderr or ""),
        )
    result = AstIndexResult(
        ok=completed.returncode == 0,
        command=list(command),
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
    if completed.returncode != 0:
        result.reason_code = REASON_INDEX_MISSING
    return result


def _parse_json_result(result: AstIndexResult) -> AstIndexResult:
    if not result.ok:
        return result
    try:
        result.payload = json.loads(result.stdout or "null")
    except json.JSONDecodeError:
        result.ok = False
        result.reason_code = REASON_JSON_INVALID
    return result


def ensure_index(
    project_root: Path,
    config: AstIndexConfig,
    *,
    allow_rebuild: bool | None = None,
) -> AstIndexResult:
    detection = detect(config)
    if not detection.ok:
        return detection

    binary = detection.binary_path
    timeout_s = config.timeout_s
    stats = _parse_json_result(
        _run_command([binary, "stats", "--format", "json"], cwd=project_root, timeout_s=timeout_s)
    )
    if stats.ok:
        stats.index_ready = True
        stats.binary_path = binary
        return stats
    if stats.reason_code in {REASON_TIMEOUT, REASON_JSON_INVALID}:
        stats.fallback_reason_code = _fallback_reason(config, stats.reason_code)
        stats.binary_path = binary
        return stats

    should_rebuild = config.auto_ensure_index if allow_rebuild is None else allow_rebuild
    if not should_rebuild:
        stats.reason_code = REASON_INDEX_MISSING
        stats.fallback_reason_code = _fallback_reason(config, stats.reason_code)
        stats.binary_path = binary
        return stats

    rebuild = _run_command([binary, "rebuild"], cwd=project_root, timeout_s=max(30, timeout_s * 4))
    if not rebuild.ok:
        rebuild.reason_code = rebuild.reason_code or REASON_INDEX_MISSING
        rebuild.fallback_reason_code = _fallback_reason(config, rebuild.reason_code)
        rebuild.binary_path = binary
        return rebuild

    stats_retry = _parse_json_result(
        _run_command([binary, "stats", "--format", "json"], cwd=project_root, timeout_s=timeout_s)
    )
    if stats_retry.ok:
        stats_retry.index_ready = True
        stats_retry.binary_path = binary
        return stats_retry
    stats_retry.reason_code = stats_retry.reason_code or REASON_INDEX_MISSING
    stats_retry.fallback_reason_code = _fallback_reason(config, stats_retry.reason_code)
    stats_retry.binary_path = binary
    return stats_retry


def _normalize_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _first_text(source: Dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        raw = source.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            return text
    return ""


def _extract_records(payload: Any) -> List[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("results", "items", "matches", "symbols", "data", "rows"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return [payload]


def normalize(payload: Any, *, max_results: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in _extract_records(payload):
        if isinstance(item, dict):
            row = {
                "symbol": _first_text(item, ("symbol", "name", "title", "identifier", "id")),
                "kind": _first_text(item, ("kind", "type", "symbol_kind", "node_kind")),
                "path": _first_text(item, ("path", "file", "file_path", "source_path", "uri", "module")),
                "line": _normalize_int(item.get("line") or item.get("line_start") or item.get("start_line")),
                "column": _normalize_int(item.get("column") or item.get("col") or item.get("start_column")),
                "score": _normalize_float(item.get("score") or item.get("rank") or item.get("confidence")),
                "snippet": _first_text(item, ("snippet", "context", "extract", "line_text", "text")),
            }
        else:
            row = {
                "symbol": str(item).strip(),
                "kind": "",
                "path": "",
                "line": 0,
                "column": 0,
                "score": 0.0,
                "snippet": "",
            }
        if not (row["symbol"] or row["path"]):
            continue
        rows.append(row)
    rows.sort(
        key=lambda row: (
            row.get("path") or "",
            int(row.get("line") or 0),
            int(row.get("column") or 0),
            row.get("symbol") or "",
            row.get("kind") or "",
            -float(row.get("score") or 0.0),
        )
    )
    return rows[: max(1, max_results)]


def run_json(
    project_root: Path,
    config: AstIndexConfig,
    command_args: Sequence[str],
    *,
    timeout_s: int | None = None,
) -> AstIndexResult:
    detection = detect(config)
    if not detection.ok:
        return detection

    ensured = ensure_index(project_root, config)
    if not ensured.ok:
        return ensured

    binary = detection.binary_path
    args = list(command_args)
    if "--format" not in args:
        args.extend(["--format", "json"])
    command = [binary, *args]
    timeout = timeout_s if timeout_s is not None else config.timeout_s
    result = _run_command(command, cwd=project_root, timeout_s=max(1, int(timeout)))
    result.binary_path = binary
    if not result.ok:
        result.reason_code = result.reason_code or REASON_INDEX_MISSING
        result.fallback_reason_code = _fallback_reason(config, result.reason_code)
        return result

    result = _parse_json_result(result)
    if not result.ok:
        result.fallback_reason_code = _fallback_reason(config, result.reason_code)
        return result

    result.normalized = normalize(result.payload, max_results=config.max_results)
    result.index_ready = True
    return result


def probe_readiness(project_root: Path, config: AstIndexConfig) -> Dict[str, Any]:
    detection = detect(config)
    data: Dict[str, Any] = {
        "mode": config.mode,
        "required": config.required,
        "binary": config.binary,
        "available": detection.ok,
        "binary_path": detection.binary_path,
        "index_ready": False,
        "reason_code": detection.reason_code,
        "fallback_reason_code": detection.fallback_reason_code,
        "version": "",
    }
    if not detection.ok:
        return data

    version = _run_command([detection.binary_path, "--version"], cwd=project_root, timeout_s=max(1, config.timeout_s))
    if version.ok:
        data["version"] = (version.stdout or "").strip().splitlines()[0] if version.stdout else ""
    else:
        data["version"] = ""

    ensured = ensure_index(project_root, config, allow_rebuild=False)
    data["index_ready"] = ensured.ok
    if not ensured.ok:
        data["reason_code"] = ensured.reason_code
        data["fallback_reason_code"] = ensured.fallback_reason_code
    else:
        data["reason_code"] = ""
        data["fallback_reason_code"] = ""
    return data


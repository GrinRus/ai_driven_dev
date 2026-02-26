from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from aidd_runtime.io_utils import read_jsonl, utc_timestamp, write_json

SCHEMA = "aidd.context_quality.v1"
AST_FALLBACK_CODES = {
    "ast_index_binary_missing",
    "ast_index_index_missing",
    "ast_index_timeout",
    "ast_index_json_invalid",
    "ast_index_fallback_rg",
}

_REASON_CODE_RE = re.compile(r"[^a-z0-9_:]+")


def artifact_path(root: Path, ticket: str) -> Path:
    return root / "reports" / "observability" / f"{ticket}.context-quality.json"


def _normalize_reason_code(value: Any) -> str:
    token = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not token:
        return ""
    return _REASON_CODE_RE.sub("", token)


def _is_pack_path(path: str) -> bool:
    normalized = str(path or "").strip().replace("\\", "/")
    return bool(normalized) and (
        ".pack." in normalized or normalized.endswith(".pack.json") or normalized.endswith(".pack.md")
    )


def _is_slice_path(path: str) -> bool:
    normalized = str(path or "").strip().replace("\\", "/")
    if not normalized:
        return False
    return any(token in normalized for token in ("-slice", "/slices/", "-chunk-"))


def _is_memory_slice_path(path: str) -> bool:
    normalized = str(path or "").strip().replace("\\", "/")
    if not normalized:
        return False
    return "-memory-slice" in normalized or "-memory-slices." in normalized


def _is_full_read_path(path: str) -> bool:
    normalized = str(path or "").strip().replace("\\", "/")
    if not normalized:
        return False
    if normalized.startswith(("aidd/docs/", "docs/")):
        return True
    if normalized.startswith("aidd/reports/") and not _is_pack_path(normalized):
        return True
    return not normalized.startswith("aidd/reports/")


def classify_read_entries(read_entries: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"pack_reads": 0, "slice_reads": 0, "memory_slice_reads": 0, "full_reads": 0}
    for entry in read_entries:
        path = str((entry or {}).get("path") or "").strip()
        if not path:
            continue
        if _is_slice_path(path):
            counts["slice_reads"] += 1
            if _is_memory_slice_path(path):
                counts["memory_slice_reads"] += 1
            continue
        if _is_pack_path(path):
            counts["pack_reads"] += 1
            if _is_memory_slice_path(path):
                counts["memory_slice_reads"] += 1
            continue
        if _is_full_read_path(path):
            counts["full_reads"] += 1
    return counts


def _default_payload(ticket: str) -> Dict[str, Any]:
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA,
        "ticket": ticket,
        "generated_at": utc_timestamp(),
        "updated_at": utc_timestamp(),
        "metrics": {
            "pack_reads": 0,
            "slice_reads": 0,
            "memory_slice_reads": 0,
            "full_reads": 0,
            "retrieval_events": 0,
            "fallback_events": 0,
            "fallback_rate": 0.0,
            "rg_invocations": 0,
            "rg_without_slice": 0,
            "rg_without_slice_rate": 0.0,
            "decisions_pack_stale_events": 0,
            "output_contract_total": 0,
            "output_contract_warns": 0,
            "output_contract_warn_rate": 0.0,
            "context_expand_count_by_reason": {},
        },
    }


def _load_payload(path: Path, ticket: str) -> Dict[str, Any]:
    if not path.exists():
        return _default_payload(ticket)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_payload(ticket)
    if not isinstance(payload, dict):
        return _default_payload(ticket)
    payload.setdefault("schema", SCHEMA)
    payload.setdefault("schema_version", SCHEMA)
    payload.setdefault("ticket", ticket)
    payload.setdefault("generated_at", utc_timestamp())
    payload.setdefault("updated_at", utc_timestamp())
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}
        payload["metrics"] = metrics
    metrics.setdefault("pack_reads", 0)
    metrics.setdefault("slice_reads", 0)
    metrics.setdefault("memory_slice_reads", 0)
    metrics.setdefault("full_reads", 0)
    metrics.setdefault("retrieval_events", 0)
    metrics.setdefault("fallback_events", 0)
    metrics.setdefault("fallback_rate", 0.0)
    metrics.setdefault("rg_invocations", 0)
    metrics.setdefault("rg_without_slice", 0)
    metrics.setdefault("rg_without_slice_rate", 0.0)
    metrics.setdefault("decisions_pack_stale_events", 0)
    metrics.setdefault("output_contract_total", 0)
    metrics.setdefault("output_contract_warns", 0)
    metrics.setdefault("output_contract_warn_rate", 0.0)
    raw_reasons = metrics.get("context_expand_count_by_reason")
    metrics["context_expand_count_by_reason"] = raw_reasons if isinstance(raw_reasons, dict) else {}
    return payload


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def collect_context_expand_counts(root: Path, ticket: str) -> Dict[str, int]:
    base = root / "reports" / "actions" / ticket
    if not base.exists():
        return {}
    counters: Dict[str, int] = {}
    for audit_path in sorted(base.glob("*/context-expand.audit.jsonl")):
        for payload in read_jsonl(audit_path):
            reason_code = _normalize_reason_code(payload.get("reason_code"))
            if not reason_code:
                continue
            counters[reason_code] = counters.get(reason_code, 0) + 1
    return dict(sorted(counters.items()))


def update_metrics(
    root: Path,
    *,
    ticket: str,
    pack_reads: int = 0,
    slice_reads: int = 0,
    memory_slice_reads: int = 0,
    full_reads: int = 0,
    retrieval_events: int = 0,
    fallback_events: int = 0,
    rg_invocations: int = 0,
    rg_without_slice: int = 0,
    decisions_pack_stale_events: int = 0,
    output_contract_total: int = 0,
    output_contract_warn: bool = False,
    context_expand_refresh: bool = False,
    source: str = "",
) -> Dict[str, Any]:
    path = artifact_path(root, ticket)
    payload = _load_payload(path, ticket)
    metrics = payload["metrics"]

    metrics["pack_reads"] = _as_int(metrics.get("pack_reads")) + max(0, _as_int(pack_reads))
    metrics["slice_reads"] = _as_int(metrics.get("slice_reads")) + max(0, _as_int(slice_reads))
    metrics["memory_slice_reads"] = _as_int(metrics.get("memory_slice_reads")) + max(0, _as_int(memory_slice_reads))
    metrics["full_reads"] = _as_int(metrics.get("full_reads")) + max(0, _as_int(full_reads))
    metrics["retrieval_events"] = _as_int(metrics.get("retrieval_events")) + max(0, _as_int(retrieval_events))
    metrics["fallback_events"] = _as_int(metrics.get("fallback_events")) + max(0, _as_int(fallback_events))
    metrics["rg_invocations"] = _as_int(metrics.get("rg_invocations")) + max(0, _as_int(rg_invocations))
    metrics["rg_without_slice"] = _as_int(metrics.get("rg_without_slice")) + max(0, _as_int(rg_without_slice))
    metrics["decisions_pack_stale_events"] = _as_int(metrics.get("decisions_pack_stale_events")) + max(
        0, _as_int(decisions_pack_stale_events)
    )
    metrics["output_contract_total"] = _as_int(metrics.get("output_contract_total")) + max(0, _as_int(output_contract_total))
    metrics["output_contract_warns"] = _as_int(metrics.get("output_contract_warns")) + (1 if output_contract_warn else 0)

    retrieval_total = max(0, _as_int(metrics.get("retrieval_events")))
    fallback_total = max(0, _as_int(metrics.get("fallback_events")))
    metrics["fallback_rate"] = round((fallback_total / retrieval_total), 6) if retrieval_total else 0.0
    rg_total = max(0, _as_int(metrics.get("rg_invocations")))
    rg_without_slice_total = max(0, _as_int(metrics.get("rg_without_slice")))
    metrics["rg_without_slice_rate"] = round((rg_without_slice_total / rg_total), 6) if rg_total else 0.0

    contract_total = max(0, _as_int(metrics.get("output_contract_total")))
    contract_warns = max(0, _as_int(metrics.get("output_contract_warns")))
    metrics["output_contract_warn_rate"] = round((contract_warns / contract_total), 6) if contract_total else 0.0

    if context_expand_refresh:
        metrics["context_expand_count_by_reason"] = collect_context_expand_counts(root, ticket)

    payload["updated_at"] = utc_timestamp()
    if source:
        payload["source"] = source
    write_json(path, payload, sort_keys=True)
    return payload


def update_from_output_contract(
    root: Path,
    *,
    ticket: str,
    read_entries: Sequence[Dict[str, Any]],
    status: str,
    reason_code: str,
    ast_reason_codes: Sequence[str],
    warnings: Sequence[str] | None = None,
) -> Dict[str, Any]:
    read_counts = classify_read_entries(read_entries)
    ast_codes = {_normalize_reason_code(code) for code in ast_reason_codes if _normalize_reason_code(code)}
    warning_codes = {
        _normalize_reason_code(item) for item in (warnings or []) if _normalize_reason_code(item)
    }
    reason_code_token = _normalize_reason_code(reason_code)
    ast_pack_seen = any(
        str((entry or {}).get("path") or "").strip().replace("\\", "/").endswith("-ast.pack.json")
        for entry in read_entries
    )
    retrieval_events = 1 if (ast_pack_seen or ast_codes) else 0
    fallback_events = 1 if ast_codes else 0
    rg_without_slice = 1 if ("rg_without_slice" in warning_codes or reason_code_token == "rg_without_slice") else 0
    decisions_pack_stale = (
        1 if ("memory_decisions_pack_stale" in warning_codes or reason_code_token == "memory_decisions_pack_stale") else 0
    )
    warn = str(status or "").strip().lower() == "warn" or reason_code_token == "output_contract_warn"
    return update_metrics(
        root,
        ticket=ticket,
        pack_reads=read_counts["pack_reads"],
        slice_reads=read_counts["slice_reads"],
        memory_slice_reads=read_counts["memory_slice_reads"],
        full_reads=read_counts["full_reads"],
        retrieval_events=retrieval_events,
        fallback_events=fallback_events,
        rg_without_slice=rg_without_slice,
        decisions_pack_stale_events=decisions_pack_stale,
        output_contract_total=1,
        output_contract_warn=warn,
        context_expand_refresh=True,
        source="output_contract",
    )


def update_from_ast(
    root: Path,
    *,
    ticket: str,
    ast_mode: str,
    ast_status: str,
    ast_reason_codes: Iterable[str],
    ast_fallback_used: bool,
    pack_reads: int = 0,
    full_reads: int = 0,
) -> Dict[str, Any]:
    mode = str(ast_mode or "").strip().lower()
    status = str(ast_status or "").strip().lower()
    normalized_codes = {_normalize_reason_code(code) for code in ast_reason_codes if _normalize_reason_code(code)}
    retrieval_events = 1 if mode and mode != "off" and status != "skipped" else 0
    fallback_events = 1 if (ast_fallback_used or bool(normalized_codes & AST_FALLBACK_CODES)) else 0
    return update_metrics(
        root,
        ticket=ticket,
        pack_reads=max(0, _as_int(pack_reads)),
        full_reads=max(0, _as_int(full_reads)),
        retrieval_events=retrieval_events,
        fallback_events=fallback_events,
        context_expand_refresh=True,
        source="research_plan",
    )


def update_from_rg_policy(
    root: Path,
    *,
    ticket: str,
    rg_without_slice: bool,
) -> Dict[str, Any]:
    return update_metrics(
        root,
        ticket=ticket,
        rg_invocations=1,
        rg_without_slice=1 if rg_without_slice else 0,
        context_expand_refresh=False,
        source="rg_guard",
    )

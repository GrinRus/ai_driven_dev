#!/usr/bin/env python3
"""Stage-aware autoslice orchestration for Memory v2 artifacts."""

from __future__ import annotations

import argparse
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Dict, List

from aidd_runtime import gates
from aidd_runtime import io_utils
from aidd_runtime import memory_common as common
from aidd_runtime import memory_slice
from aidd_runtime import runtime
from aidd_runtime import stage_lexicon


def _normalize_stage(value: str) -> str:
    return stage_lexicon.resolve_stage_name(str(value or "").strip())


def _parse_queries(raw: List[str], *, stage: str, policy: Dict[str, Any]) -> List[str]:
    tokens: List[str] = []
    for item in raw:
        for part in str(item or "").replace(";", ",").split(","):
            text = str(part or "").strip()
            if text:
                tokens.append(text)
    if not tokens:
        stage_queries = policy.get("stage_queries") if isinstance(policy.get("stage_queries"), dict) else {}
        defaults = stage_queries.get(stage) if isinstance(stage_queries.get(stage), list) else []
        tokens = [str(item).strip() for item in defaults if str(item).strip()]
    deduped: List[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)
    return deduped


def _policy_with_gate_overrides(project_root: Path, base_policy: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base_policy)
    try:
        gates_cfg = gates.load_gates_config(project_root)
    except Exception:
        gates_cfg = {}
    memory_cfg = gates_cfg.get("memory") if isinstance(gates_cfg.get("memory"), dict) else {}
    raw_mode = str(memory_cfg.get("slice_enforcement") or "").strip().lower()
    if raw_mode in {"off", "warn", "hard"}:
        merged["mode"] = raw_mode
    raw_stages = memory_cfg.get("enforce_stages")
    if isinstance(raw_stages, list):
        stages = []
        seen: set[str] = set()
        for item in raw_stages:
            stage = stage_lexicon.resolve_stage_name(str(item).strip())
            if not stage or stage in seen:
                continue
            seen.add(stage)
            stages.append(stage)
        if stages:
            merged["enforce_stages"] = stages
    raw_age = memory_cfg.get("max_slice_age_minutes")
    if raw_age is not None:
        try:
            merged["max_slice_age_minutes"] = max(1, int(raw_age))
        except (TypeError, ValueError):
            pass
    raw_rg_policy = str(memory_cfg.get("rg_policy") or "").strip().lower()
    if raw_rg_policy in {"free", "controlled_fallback", "deny"}:
        merged["rg_policy"] = raw_rg_policy
    return merged


def _run_slice(
    *,
    ticket: str,
    stage: str,
    scope_key: str,
    query: str,
    manifest_path: Path,
    project_root: Path,
) -> Dict[str, Any]:
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    cmd = [
        "--ticket",
        ticket,
        "--query",
        query,
        "--stage",
        stage,
        "--scope-key",
        scope_key,
        "--manifest",
        runtime.rel_path(manifest_path, project_root),
        "--format",
        "json",
    ]
    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            rc = int(memory_slice.main(cmd))
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "status": "error",
            "query": query,
            "reason": str(exc),
            "slice_pack": "",
            "hits": 0,
        }

    parsed: Dict[str, Any] = {}
    stdout_text = stdout_buffer.getvalue().strip()
    if stdout_text:
        try:
            payload = json.loads(stdout_text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            parsed = payload
        else:
            for line in reversed(stdout_text.splitlines()):
                line = line.strip()
                if not line:
                    continue
                try:
                    payload_line = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload_line, dict):
                    parsed = payload_line
                    break

    if rc != 0:
        reason = stderr_buffer.getvalue().strip() or "memory_slice_failed"
        return {
            "status": "error",
            "query": query,
            "reason": reason,
            "slice_pack": "",
            "hits": 0,
        }

    return {
        "status": "ok",
        "query": query,
        "reason": "",
        "slice_pack": str(parsed.get("slice_pack") or ""),
        "stage_latest_pack": str(parsed.get("stage_latest_pack") or ""),
        "manifest_pack": str(parsed.get("manifest_pack") or ""),
        "hits": int(parsed.get("hits") or 0),
    }


def _ensure_placeholder_manifest(
    *,
    manifest_path: Path,
    ticket: str,
    stage: str,
    scope_key: str,
) -> None:
    if manifest_path.exists():
        return
    payload = {
        "schema": "aidd.memory.slices.manifest.v1",
        "schema_version": "aidd.memory.slices.manifest.v1",
        "pack_version": "v1",
        "type": "memory-slices-manifest",
        "kind": "pack",
        "ticket": ticket,
        "slug_hint": ticket,
        "stage": stage,
        "scope_key": scope_key,
        "generated_at": io_utils.utc_timestamp(),
        "updated_at": io_utils.utc_timestamp(),
        "stats": {
            "max_slices": 0,
            "max_chars": 0,
            "trimmed": False,
            "slice_count": 0,
            "placeholder": True,
        },
        "slices": {
            "cols": ["query", "slice_pack", "latest_alias", "hits"],
            "rows": [],
        },
    }
    io_utils.write_json(manifest_path, payload, sort_keys=True)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate stage-aware memory slice manifest for active feature.")
    parser.add_argument("--ticket", help="Ticket identifier (defaults to docs/.active.json).")
    parser.add_argument("--stage", help="Stage label (defaults to docs/.active.json).")
    parser.add_argument("--scope-key", help="Scope key override (defaults to active work item).")
    parser.add_argument(
        "--queries",
        action="append",
        default=[],
        help="Optional comma-separated queries; can be repeated.",
    )
    parser.add_argument("--max-slices", type=int, help="Optional cap for generated queries.")
    parser.add_argument("--manifest", help="Optional explicit output path for manifest.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        _, project_root = runtime.require_workflow_root(Path.cwd())
        ticket, _ = runtime.require_ticket(project_root, ticket=args.ticket, slug_hint=None)
        stage = _normalize_stage(args.stage or runtime.read_active_stage(project_root) or "")
        if not stage:
            raise ValueError("stage is required (pass --stage or set active stage)")
        scope_key = str(args.scope_key or "").strip() or runtime.resolve_scope_key(runtime.read_active_work_item(project_root), ticket)

        settings = common.load_memory_settings(project_root)
        policy = _policy_with_gate_overrides(project_root, common.slice_policy(settings))
        mode = str(policy.get("mode") or "warn").strip().lower()
        enforce_stages = {
            stage
            for stage in (
                stage_lexicon.resolve_stage_name(str(item).strip())
                for item in (policy.get("enforce_stages") or [])
                if str(item).strip()
            )
            if stage
        }

        queries = _parse_queries(args.queries, stage=stage, policy=policy)
        max_slices = int(args.max_slices or policy["manifest_budget"]["max_slices"])
        queries = queries[: max(1, max_slices)]
        if not queries:
            raise ValueError("no queries resolved for autoslice")

        manifest_path = (
            runtime.resolve_path_for_target(Path(args.manifest), project_root)
            if args.manifest
            else common.memory_slices_manifest_path(project_root, ticket, stage, scope_key)
        )

        results: List[Dict[str, Any]] = []
        for query in queries:
            results.append(
                _run_slice(
                    ticket=ticket,
                    stage=stage,
                    scope_key=scope_key,
                    query=query,
                    manifest_path=manifest_path,
                    project_root=project_root,
                )
            )

        ok_rows = [row for row in results if row.get("status") == "ok"]
        status = "ok"
        reason_code = ""
        if not ok_rows:
            if mode == "hard" and stage in enforce_stages:
                status = "blocked"
                reason_code = "memory_slice_missing"
            else:
                status = "warn"
                reason_code = "memory_slice_missing_warn"
            _ensure_placeholder_manifest(
                manifest_path=manifest_path,
                ticket=ticket,
                stage=stage,
                scope_key=scope_key,
            )

        payload = {
            "schema": "aidd.memory.autoslice.result.v1",
            "status": status,
            "reason_code": reason_code,
            "ticket": ticket,
            "stage": stage,
            "scope_key": scope_key,
            "manifest_pack": runtime.rel_path(manifest_path, project_root) if manifest_path.exists() else "",
            "queries_total": len(queries),
            "queries_ok": len(ok_rows),
            "rows": [
                {
                    "query": str(row.get("query") or ""),
                    "status": str(row.get("status") or ""),
                    "slice_pack": str(row.get("slice_pack") or ""),
                    "stage_latest_pack": str(row.get("stage_latest_pack") or ""),
                    "hits": int(row.get("hits") or 0),
                    "reason": str(row.get("reason") or ""),
                }
                for row in results
            ],
        }

        if args.format == "json":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"manifest_pack={payload['manifest_pack']}")
            print(
                "summary="
                f"stage={stage} scope={scope_key} queries={payload['queries_total']} ok={payload['queries_ok']} status={status}"
            )
            if reason_code:
                print(f"reason_code={reason_code}")

        if status == "blocked":
            return 2
        return 0
    except Exception as exc:
        print(f"[memory-autoslice] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

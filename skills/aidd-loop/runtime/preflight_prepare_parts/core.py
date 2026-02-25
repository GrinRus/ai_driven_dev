#!/usr/bin/env python3
"""Generate loop-stage preflight artifacts (maps, actions template, preflight result)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from aidd_runtime import actions_validate
from aidd_runtime import context_map_validate
from aidd_runtime import preflight_result_validate
from aidd_runtime import runtime
from aidd_runtime import skill_contract_validate
from aidd_runtime.diff_boundary_check import extract_boundaries, parse_front_matter
from aidd_runtime.io_utils import utc_timestamp, write_json

DEFAULT_ACTION_TYPES = [
    "tasklist_ops.set_iteration_done",
    "tasklist_ops.append_progress_log",
    "tasklist_ops.next3_recompute",
    "context_pack_ops.context_pack_update",
]
ALWAYS_ALLOW_REPORTS = ["aidd/reports/**", "aidd/reports/actions/**"]


class PreflightBlocked(RuntimeError):
    def __init__(self, reason_code: str, reason: str) -> None:
        super().__init__(reason)
        self.reason_code = reason_code
        self.reason = reason


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:  # pragma: no cover - defensive
        return "{" + key + "}"


def _render_template(value: str, context: Dict[str, str]) -> str:
    return str(value).format_map(_SafeDict(context))


def _render_items(items: Iterable[str], context: Dict[str, str]) -> List[str]:
    rendered: List[str] = []
    for item in items:
        text = _render_template(str(item), context).strip()
        if text:
            rendered.append(text)
    return rendered


def _parse_ref(ref: str) -> Tuple[str, str]:
    raw = str(ref or "").strip()
    if not raw:
        return "", ""
    if "#AIDD:" in raw:
        path, selector = raw.split("#", 1)
        return path.strip(), f"#{selector.strip()}"
    if "@handoff:" in raw:
        path, marker = raw.split("@handoff:", 1)
        return path.strip(), f"@handoff:{marker.strip()}"
    return raw, ""


def _contract_entries(items: Any, context: Dict[str, str], *, required: bool) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if not isinstance(items, list):
        return entries
    for item in items:
        reason = "contract.required" if required else "contract.optional"
        if isinstance(item, str):
            ref = _render_template(item, context)
        elif isinstance(item, dict):
            ref = _render_template(str(item.get("ref") or ""), context)
            custom_reason = str(item.get("reason") or "").strip()
            if custom_reason:
                reason = custom_reason
        else:
            continue
        path, selector = _parse_ref(ref)
        if not path:
            continue
        entries.append(
            {
                "ref": ref,
                "path": path,
                "selector": selector,
                "required": required,
                "reason": reason,
            }
        )
    return entries


def _dedupe_str(items: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _resolve_rel(path_value: str, target: Path) -> str:
    return runtime.rel_path(runtime.resolve_path_for_target(Path(path_value), target), target)


def _read_loop_allowed_paths(loop_pack_path: Path) -> List[str]:
    if not loop_pack_path.exists():
        return []
    lines = loop_pack_path.read_text(encoding="utf-8").splitlines()
    allowed, _ = extract_boundaries(parse_front_matter(lines))
    return _dedupe_str(allowed)


def _render_readmap_md(readmap: Dict[str, Any]) -> str:
    lines = [
        "# Read Map",
        "",
        f"- schema: {readmap.get('schema')}",
        f"- ticket: {readmap.get('ticket')}",
        f"- stage: {readmap.get('stage')}",
        f"- scope_key: {readmap.get('scope_key')}",
        f"- work_item_key: {readmap.get('work_item_key')}",
        f"- generated_at: {readmap.get('generated_at')}",
        "",
        "## Required",
    ]
    required_entries = [entry for entry in readmap.get("entries", []) if entry.get("required")]
    optional_entries = [entry for entry in readmap.get("entries", []) if not entry.get("required")]
    if required_entries:
        for entry in required_entries:
            selector = entry.get("selector") or ""
            suffix = f" {selector}" if selector else ""
            lines.append(f"- {entry.get('path')}{suffix} (reason: {entry.get('reason')})")
    else:
        lines.append("- (none)")
    lines.extend(["", "## Optional"])
    if optional_entries:
        for entry in optional_entries:
            selector = entry.get("selector") or ""
            suffix = f" {selector}" if selector else ""
            lines.append(f"- {entry.get('path')}{suffix} (reason: {entry.get('reason')})")
    else:
        lines.append("- (none)")

    lines.extend(["", "## Allowed Paths"])
    for item in readmap.get("allowed_paths", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Loop Allowed Paths"])
    loop_paths = readmap.get("loop_allowed_paths") or []
    if loop_paths:
        for item in loop_paths:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")

    return "\n".join(lines).rstrip() + "\n"


def _render_writemap_md(writemap: Dict[str, Any]) -> str:
    lines = [
        "# Write Map",
        "",
        f"- schema: {writemap.get('schema')}",
        f"- ticket: {writemap.get('ticket')}",
        f"- stage: {writemap.get('stage')}",
        f"- scope_key: {writemap.get('scope_key')}",
        f"- work_item_key: {writemap.get('work_item_key')}",
        f"- generated_at: {writemap.get('generated_at')}",
        "",
        "## Allowed Paths",
    ]
    for item in writemap.get("allowed_paths", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Loop Allowed Paths"])
    loop_allowed = writemap.get("loop_allowed_paths") or []
    if loop_allowed:
        for item in loop_allowed:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")
    lines.extend(["", "## DocOps Only Paths"])
    docops_only = writemap.get("docops_only_paths") or []
    if docops_only:
        for item in docops_only:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")
    lines.extend(["", "## Always Allow"])
    for item in writemap.get("always_allow", []):
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"

def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run_loop_pack(target: Path, *, ticket: str, stage: str, work_item_key: str) -> Dict[str, Any]:
    if stage == "review":
        loop_stage = "review"
    else:
        loop_stage = "implement"
    plugin_root = runtime.require_plugin_root()
    cmd = [
        sys.executable,
        str(plugin_root / "skills" / "aidd-loop" / "runtime" / "loop_pack.py"),
        "--ticket",
        ticket,
        "--stage",
        loop_stage,
        "--work-item",
        work_item_key,
        "--format",
        "json",
    ]
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    env["PYTHONPATH"] = str(plugin_root) if not env.get("PYTHONPATH") else f"{plugin_root}:{env['PYTHONPATH']}"
    proc = subprocess.run(cmd, cwd=target, text=True, capture_output=True, env=env)
    raw = (proc.stdout or "").strip()
    payload: Dict[str, Any] = {}
    if raw:
        try:
            maybe = json.loads(raw)
            if isinstance(maybe, dict):
                payload = maybe
        except json.JSONDecodeError:
            payload = {}

    if proc.returncode != 0:
        reason_code = str(payload.get("reason") or "loop_pack_failed").strip() or "loop_pack_failed"
        reason = str(payload.get("message") or payload.get("reason") or proc.stderr or proc.stdout).strip()
        raise PreflightBlocked(reason_code, reason or "loop-pack failed")

    if payload.get("status") == "blocked":
        reason_code = str(payload.get("reason") or "loop_pack_blocked").strip() or "loop_pack_blocked"
        reason = str(payload.get("message") or reason_code).strip()
        raise PreflightBlocked(reason_code, reason)

    required = ("path", "scope_key", "work_item_key")
    if not all(payload.get(key) for key in required):
        raise PreflightBlocked("loop_pack_payload_invalid", "loop-pack returned incomplete payload")

    return payload


def _allowed_artifact_paths(target: Path, context: Dict[str, str]) -> Dict[str, List[Path]]:
    ticket = context["ticket"]
    scope_key = context["scope_key"]
    stage = context["stage"]
    actions_dir = target / "reports" / "actions" / ticket / scope_key
    context_dir = target / "reports" / "context" / ticket
    loops_dir = target / "reports" / "loops" / ticket / scope_key
    return {
        "actions_template": [actions_dir / f"{stage}.actions.template.json"],
        "readmap_json": [context_dir / f"{scope_key}.readmap.json"],
        "readmap_md": [context_dir / f"{scope_key}.readmap.md"],
        "writemap_json": [context_dir / f"{scope_key}.writemap.json"],
        "writemap_md": [context_dir / f"{scope_key}.writemap.md"],
        "result": [loops_dir / "stage.preflight.result.json"],
    }


def _validate_artifact_paths(
    *,
    target: Path,
    provided: Dict[str, Path],
    allowed: Dict[str, List[Path]],
) -> None:
    mismatches: List[str] = []
    for key, allowed_paths in allowed.items():
        provided_path = provided.get(key)
        if provided_path is None:
            continue
        provided_resolved = provided_path.resolve()
        allowed_resolved = [path.resolve() for path in allowed_paths]
        if provided_resolved in allowed_resolved:
            continue
        expected_text = " | ".join(runtime.rel_path(path, target) for path in allowed_paths)
        mismatches.append(
            f"{key}: expected one of [{expected_text}] provided={runtime.rel_path(provided_path, target)}"
        )
    if mismatches:
        raise PreflightBlocked("artifact_path_mismatch", "; ".join(mismatches))


def _build_readmap(
    *,
    contract: Dict[str, Any],
    context: Dict[str, str],
    target: Path,
    loop_pack_rel: str,
    review_pack_rel: str,
    loop_allowed_paths: List[str],
) -> Dict[str, Any]:
    reads = contract.get("reads") if isinstance(contract, dict) else {}
    required_entries = _contract_entries((reads or {}).get("required"), context, required=True)
    optional_entries = _contract_entries((reads or {}).get("optional"), context, required=False)

    if loop_pack_rel and loop_pack_rel not in [entry["path"] for entry in required_entries + optional_entries]:
        required_entries.insert(
            0,
            {
                "ref": loop_pack_rel,
                "path": loop_pack_rel,
                "selector": "",
                "required": True,
                "reason": "loop-pack",
            },
        )

    if review_pack_rel and review_pack_rel not in [entry["path"] for entry in required_entries + optional_entries]:
        optional_entries.append(
            {
                "ref": review_pack_rel,
                "path": review_pack_rel,
                "selector": "",
                "required": False,
                "reason": "review-pack",
            }
        )

    entries = required_entries + optional_entries
    allowed_paths = _dedupe_str([entry["path"] for entry in entries] + ALWAYS_ALLOW_REPORTS)
    readmap = {
        "schema": "aidd.readmap.v1",
        "ticket": context["ticket"],
        "stage": context["stage"],
        "scope_key": context["scope_key"],
        "work_item_key": context["work_item_key"],
        "generated_at": utc_timestamp(),
        "source_contract": runtime.rel_path(Path(context["contract_path"]), target),
        "entries": entries,
        "allowed_paths": allowed_paths,
        "loop_allowed_paths": _dedupe_str(loop_allowed_paths),
        "always_allow": ALWAYS_ALLOW_REPORTS,
    }
    return readmap


def _build_writemap(
    *,
    contract: Dict[str, Any],
    context: Dict[str, str],
    target: Path,
    loop_allowed_paths: List[str],
) -> Dict[str, Any]:
    writes = contract.get("writes") if isinstance(contract, dict) else {}
    outputs = contract.get("outputs") if isinstance(contract, dict) else []

    files = _render_items((writes or {}).get("files") or [], context)
    patterns = _render_items((writes or {}).get("patterns") or [], context)
    rendered_outputs = _render_items(outputs if isinstance(outputs, list) else [], context)

    via = (writes or {}).get("via") or {}
    docops_only_paths = _render_items((via or {}).get("docops_only") or [], context)

    write_blocks = _render_items((writes or {}).get("blocks") or [], context)

    allowed_paths = _dedupe_str(files + patterns + rendered_outputs + list(loop_allowed_paths) + ALWAYS_ALLOW_REPORTS)
    writemap = {
        "schema": "aidd.writemap.v1",
        "ticket": context["ticket"],
        "stage": context["stage"],
        "scope_key": context["scope_key"],
        "work_item_key": context["work_item_key"],
        "generated_at": utc_timestamp(),
        "source_contract": runtime.rel_path(Path(context["contract_path"]), target),
        "allowed_paths": allowed_paths,
        "loop_allowed_paths": _dedupe_str(loop_allowed_paths),
        "docops_only_paths": _dedupe_str(docops_only_paths),
        "always_allow": ALWAYS_ALLOW_REPORTS,
        "write_blocks": write_blocks,
    }
    return writemap


def _build_actions_template(contract: Dict[str, Any], context: Dict[str, str]) -> Dict[str, Any]:
    actions = contract.get("actions") if isinstance(contract, dict) else {}
    allowed_types = actions.get("allowed_types") if isinstance(actions, dict) else None
    if not isinstance(allowed_types, list) or not allowed_types:
        allowed_types = list(DEFAULT_ACTION_TYPES)

    payload = {
        "schema_version": "aidd.actions.v1",
        "stage": context["stage"],
        "ticket": context["ticket"],
        "scope_key": context["scope_key"],
        "work_item_key": context["work_item_key"],
        "allowed_action_types": _dedupe_str(str(item) for item in allowed_types),
        "actions": [],
    }
    errors = actions_validate.validate_actions_data(payload)
    if errors:
        raise PreflightBlocked("actions_template_invalid", "; ".join(errors))
    return payload


def _build_preflight_result(
    *,
    status: str,
    reason_code: str,
    reason: str,
    context: Dict[str, str],
    artifacts: Dict[str, str],
) -> Dict[str, Any]:
    normalized_status = str(status or "").strip().lower() or "blocked"
    normalized_reason_code = str(reason_code or "").strip().lower()
    normalized_reason = str(reason or "").strip()
    result_value = "done" if normalized_status == "ok" else "blocked"
    payload: Dict[str, Any] = {
        "schema": "aidd.stage_result.v1",
        "schema_version": "aidd.stage_result.v1",
        "ticket": context["ticket"],
        "stage": "preflight",
        "scope_key": context["scope_key"],
        "work_item_key": context["work_item_key"],
        "result": result_value,
        "status": normalized_status,
        "reason_code": normalized_reason_code,
        "reason": normalized_reason,
        "updated_at": utc_timestamp(),
        "details": {
            "preflight_status": normalized_status,
            "target_stage": context["stage"],
            "contract": context["contract_rel"],
            "artifacts": dict(sorted(artifacts.items())),
        },
    }
    errors = preflight_result_validate.validate_preflight_result_data(payload)
    if errors:
        raise PreflightBlocked("preflight_result_invalid", "; ".join(errors))
    return payload


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate preflight artifacts for loop stages.")
    parser.add_argument("--ticket", required=True)
    parser.add_argument("--scope-key", required=True)
    parser.add_argument("--work-item-key", required=True)
    parser.add_argument("--stage", required=True, choices=("implement", "review", "qa"))
    parser.add_argument("--actions-template", required=True)
    parser.add_argument("--readmap-json", required=True)
    parser.add_argument("--readmap-md", required=True)
    parser.add_argument("--writemap-json", required=True)
    parser.add_argument("--writemap-md", required=True)
    parser.add_argument("--result", required=True, help="Path to stage.preflight.result.json")
    parser.add_argument("--contract", help="Override CONTRACT.yaml path")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root(Path.cwd())

    actions_template_path = runtime.resolve_path_for_target(Path(args.actions_template), target)
    readmap_json_path = runtime.resolve_path_for_target(Path(args.readmap_json), target)
    readmap_md_path = runtime.resolve_path_for_target(Path(args.readmap_md), target)
    writemap_json_path = runtime.resolve_path_for_target(Path(args.writemap_json), target)
    writemap_md_path = runtime.resolve_path_for_target(Path(args.writemap_md), target)
    result_path = runtime.resolve_path_for_target(Path(args.result), target)

    contract_path = (
        runtime.resolve_path_for_target(Path(args.contract), target)
        if args.contract
        else (runtime.require_plugin_root() / "skills" / args.stage / "CONTRACT.yaml")
    )

    requested_scope_key = str(args.scope_key).strip()
    work_item_key = str(args.work_item_key).strip()
    canonical_iteration_scope = ""
    if runtime.is_iteration_work_item_key(work_item_key):
        canonical_iteration_scope = runtime.resolve_scope_key(work_item_key, str(args.ticket).strip())

    context = {
        "ticket": str(args.ticket).strip(),
        "scope_key": canonical_iteration_scope or requested_scope_key,
        "work_item_key": work_item_key,
        "stage": str(args.stage).strip(),
        "contract_path": str(contract_path),
        "contract_rel": runtime.rel_path(contract_path, target),
        "requested_scope_key": requested_scope_key,
        "canonical_iteration_scope": canonical_iteration_scope,
    }

    provided_paths: Dict[str, Path] = {
        "actions_template": actions_template_path,
        "readmap_json": readmap_json_path,
        "readmap_md": readmap_md_path,
        "writemap_json": writemap_json_path,
        "writemap_md": writemap_md_path,
        "result": result_path,
    }
    allowed_paths = _allowed_artifact_paths(target, context)
    canonical_result_path = allowed_paths["result"][0].resolve()
    if provided_paths["result"].resolve() != canonical_result_path:
        # Never emit preflight result into non-canonical scope path.
        result_path = allowed_paths["result"][0]

    artifacts: Dict[str, str] = {
        "actions_template": runtime.rel_path(provided_paths["actions_template"], target),
        "readmap_json": runtime.rel_path(provided_paths["readmap_json"], target),
        "readmap_md": runtime.rel_path(provided_paths["readmap_md"], target),
        "writemap_json": runtime.rel_path(provided_paths["writemap_json"], target),
        "writemap_md": runtime.rel_path(provided_paths["writemap_md"], target),
    }

    try:
        if not context["work_item_key"]:
            raise PreflightBlocked("work_item_key_missing", "work_item_key is required for loop-stage preflight")

        requested_scope = str(context.get("requested_scope_key") or "").strip()
        canonical_scope = str(context.get("canonical_iteration_scope") or "").strip()
        if canonical_scope and requested_scope and requested_scope != canonical_scope:
            raise PreflightBlocked(
                "scope_key_not_canonical",
                f"scope_key '{requested_scope}' is non-canonical for work_item_key '{context['work_item_key']}' "
                f"(expected '{canonical_scope}')",
            )

        if not contract_path.exists():
            raise PreflightBlocked("contract_missing", f"contract not found: {context['contract_rel']}")

        try:
            contract = skill_contract_validate.load_contract(contract_path)
        except Exception as exc:
            raise PreflightBlocked("contract_invalid", str(exc))
        contract_errors = skill_contract_validate.validate_contract_data(contract, contract_path=contract_path)
        if contract_errors:
            raise PreflightBlocked("contract_invalid", "; ".join(contract_errors))

        loop_payload = _run_loop_pack(
            target,
            ticket=context["ticket"],
            stage=context["stage"],
            work_item_key=context["work_item_key"],
        )
        loop_scope = str(loop_payload.get("scope_key") or "").strip()
        if loop_scope and loop_scope != context["scope_key"]:
            raise PreflightBlocked(
                "scope_key_mismatch",
                f"loop-pack selected scope '{loop_scope}' but preflight scope is '{context['scope_key']}'",
            )
        _validate_artifact_paths(target=target, provided=provided_paths, allowed=allowed_paths)

        loop_pack_rel = str(loop_payload.get("path") or "").strip()
        if not loop_pack_rel:
            raise PreflightBlocked("loop_pack_missing", "loop-pack path is missing in payload")
        artifacts["loop_pack"] = loop_pack_rel
        loop_pack_path = runtime.resolve_path_for_target(Path(loop_pack_rel), target)

        review_pack_path = target / "reports" / "loops" / context["ticket"] / context["scope_key"] / "review.latest.pack.md"
        review_pack_rel = runtime.rel_path(review_pack_path, target) if review_pack_path.exists() else ""
        if review_pack_rel:
            artifacts["review_pack"] = review_pack_rel

        loop_allowed_paths = _read_loop_allowed_paths(loop_pack_path)

        readmap = _build_readmap(
            contract=contract,
            context=context,
            target=target,
            loop_pack_rel=loop_pack_rel,
            review_pack_rel=review_pack_rel,
            loop_allowed_paths=loop_allowed_paths,
        )
        writemap = _build_writemap(
            contract=contract,
            context=context,
            target=target,
            loop_allowed_paths=loop_allowed_paths,
        )
        actions_template = _build_actions_template(contract, context)
        readmap_errors = context_map_validate.validate_context_map_data(readmap)
        if readmap_errors:
            raise PreflightBlocked("readmap_invalid", "; ".join(readmap_errors))
        writemap_errors = context_map_validate.validate_context_map_data(writemap)
        if writemap_errors:
            raise PreflightBlocked("writemap_invalid", "; ".join(writemap_errors))

        write_json(readmap_json_path, readmap, sort_keys=True)
        _write_text(readmap_md_path, _render_readmap_md(readmap))
        write_json(writemap_json_path, writemap, sort_keys=True)
        _write_text(writemap_md_path, _render_writemap_md(writemap))
        write_json(actions_template_path, actions_template, sort_keys=True)

        result_payload = _build_preflight_result(
            status="ok",
            reason_code="",
            reason="",
            context=context,
            artifacts=artifacts,
        )
        write_json(result_path, result_payload, sort_keys=True)

        output = {
            "schema": "aidd.preflight_prepare.result.v1",
            "status": "ok",
            "ticket": context["ticket"],
            "stage": context["stage"],
            "scope_key": context["scope_key"],
            "work_item_key": context["work_item_key"],
            "artifacts": artifacts,
            "result_path": runtime.rel_path(result_path, target),
        }
        if args.format == "json":
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            print(f"loop_pack_path={artifacts.get('loop_pack', '')}")
            if artifacts.get("review_pack"):
                print(f"review_pack_path={artifacts['review_pack']}")
            print(f"readmap_path={artifacts['readmap_json']}")
            print(f"writemap_path={artifacts['writemap_json']}")
            print(f"template_path={artifacts['actions_template']}")
            print(f"preflight_result={output['result_path']}")
            print("summary=preflight ok")
        return 0
    except PreflightBlocked as exc:
        blocked_payload = _build_preflight_result(
            status="blocked",
            reason_code=exc.reason_code,
            reason=exc.reason,
            context=context,
            artifacts=artifacts,
        )
        write_json(result_path, blocked_payload, sort_keys=True)
        if args.format == "json":
            print(
                json.dumps(
                    {
                        "schema": "aidd.preflight_prepare.result.v1",
                        "status": "blocked",
                        "ticket": context["ticket"],
                        "stage": context["stage"],
                        "scope_key": context["scope_key"],
                        "work_item_key": context["work_item_key"],
                        "reason_code": exc.reason_code,
                        "reason": exc.reason,
                        "result_path": runtime.rel_path(result_path, target),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(f"preflight_result={runtime.rel_path(result_path, target)}")
            print(f"summary=BLOCKED reason_code={exc.reason_code} reason={exc.reason}")
        return 2
    except Exception as exc:  # pragma: no cover - defensive
        reason = str(exc).strip() or exc.__class__.__name__
        blocked_payload = _build_preflight_result(
            status="blocked",
            reason_code="preflight_internal_error",
            reason=reason,
            context=context,
            artifacts=artifacts,
        )
        write_json(result_path, blocked_payload, sort_keys=True)
        if args.format == "json":
            print(
                json.dumps(
                    {
                        "schema": "aidd.preflight_prepare.result.v1",
                        "status": "blocked",
                        "ticket": context["ticket"],
                        "stage": context["stage"],
                        "scope_key": context["scope_key"],
                        "work_item_key": context["work_item_key"],
                        "reason_code": "preflight_internal_error",
                        "reason": reason,
                        "result_path": runtime.rel_path(result_path, target),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(f"preflight_result={runtime.rel_path(result_path, target)}")
            print(f"summary=BLOCKED reason_code=preflight_internal_error reason={reason}")
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

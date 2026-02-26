from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import re
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Iterable, Optional

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(_PLUGIN_ROOT))
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from aidd_runtime import research_hints as prd_hints
from aidd_runtime import (
    ast_index,
    context_quality,
    memory_autoslice,
    memory_extract,
    reports_pack,
    rlm_finalize,
    rlm_manifest,
    rlm_nodes_build,
    rlm_targets,
    runtime,
    tasks_derive,
)
from aidd_runtime.feature_ids import write_active_state
from aidd_runtime.rlm_config import load_rlm_settings

_TEMPLATE_MARKER_RE = re.compile(r"\{\{[^{}]+\}\}")


def _render_template(template_text: str, replacements: dict[str, str]) -> str:
    content = template_text
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def _replace_template_markers(text: str, replacement: str = "TBD") -> str:
    if not text:
        return text
    return _TEMPLATE_MARKER_RE.sub(replacement, text)


def _extract_section_body(text: str, heading: str) -> list[str] | None:
    lines = text.splitlines()
    heading_line = f"## {heading}"
    for idx, line in enumerate(lines):
        if line.strip() != heading_line:
            continue
        body: list[str] = []
        cursor = idx + 1
        while cursor < len(lines) and not lines[cursor].startswith("## "):
            body.append(lines[cursor])
            cursor += 1
        return body
    return None


def _upsert_header_field(text: str, field: str, value: str) -> str:
    lines = text.splitlines()
    prefix = f"{field}:"
    new_line = f"{prefix} {value}".rstrip()
    for idx, line in enumerate(lines):
        if line.startswith(prefix):
            lines[idx] = new_line
            return "\n".join(lines).rstrip() + "\n"

    insert_at = 0
    if lines and lines[0].startswith("#"):
        insert_at = 1
        while insert_at < len(lines) and lines[insert_at].strip() == "":
            insert_at += 1
    lines.insert(insert_at, new_line)
    return "\n".join(lines).rstrip() + "\n"


def _doc_status_from_rlm(rlm_status: str) -> str:
    normalized = (rlm_status or "").strip().lower()
    if normalized == "ready":
        return "reviewed"
    if normalized == "warn":
        return "warn"
    return "pending"


def _ensure_research_doc(
    target: Path,
    ticket: str,
    slug_hint: Optional[str],
    *,
    template_overrides: Optional[dict[str, str]] = None,
) -> tuple[Optional[Path], str]:
    template = target / "docs" / "research" / "template.md"
    destination = target / "docs" / "research" / f"{ticket}.md"
    if not template.exists():
        return None, "missing_template"
    destination.parent.mkdir(parents=True, exist_ok=True)
    template_text = template.read_text(encoding="utf-8")
    feature_label = slug_hint or ticket
    replacements = {
        "{{feature}}": feature_label,
        "{{ticket}}": ticket,
        "{{slug}}": slug_hint or "",
        "{{slug_hint}}": slug_hint or "",
        "{{date}}": dt.date.today().isoformat(),
        "{{owner}}": os.getenv("GIT_AUTHOR_NAME")
        or os.getenv("GIT_COMMITTER_NAME")
        or os.getenv("USER")
        or "",
    }
    if template_overrides:
        replacements.update(template_overrides)
    rendered = _replace_template_markers(_render_template(template_text, replacements))
    if not destination.exists():
        destination.write_text(rendered, encoding="utf-8")
        return destination, "created"

    current = destination.read_text(encoding="utf-8")
    updated = current
    updated = _upsert_header_field(updated, "Status", replacements.get("{{doc_status}}", "pending"))
    updated = _upsert_header_field(updated, "Last reviewed", replacements.get("{{date}}", dt.date.today().isoformat()))
    for heading in ("AIDD:CONTEXT_PACK", "AIDD:PRD_OVERRIDES", "AIDD:RLM_EVIDENCE", "AIDD:AST_EVIDENCE"):
        section_body = _extract_section_body(rendered, heading)
        if section_body is None:
            continue
        updated = _replace_section(updated, heading, section_body)
    updated = _replace_template_markers(updated)

    if updated != current:
        destination.write_text(updated, encoding="utf-8")
        return destination, "updated"
    return destination, "unchanged"


def _extract_prd_overrides(prd_text: str) -> list[str]:
    overrides: list[str] = []
    for line in prd_text.splitlines():
        if re.search(r"USER OVERRIDE", line, re.IGNORECASE):
            overrides.append(line.strip())
    return overrides


def _render_overrides_block(overrides: list[str]) -> list[str]:
    if not overrides:
        return ["- none"]
    return [f"- {line}" for line in overrides]


def _replace_section(text: str, heading: str, body_lines: list[str]) -> str:
    lines = text.splitlines()
    out: list[str] = []
    found = False
    idx = 0
    heading_line = f"## {heading}"
    while idx < len(lines):
        line = lines[idx]
        if line.strip() == heading_line:
            found = True
            out.append(heading_line)
            out.extend(body_lines)
            idx += 1
            while idx < len(lines) and not lines[idx].startswith("## "):
                idx += 1
            continue
        out.append(line)
        idx += 1
    if not found:
        if out and out[-1].strip():
            out.append("")
        out.append(heading_line)
        out.extend(body_lines)
    result = "\n".join(out).rstrip() + "\n"
    return result


def _sync_prd_overrides(
    target: Path,
    *,
    ticket: str,
    overrides: list[str],
) -> None:
    research_path = target / "docs" / "research" / f"{ticket}.md"
    if not research_path.exists():
        return
    text = research_path.read_text(encoding="utf-8")
    updated = _replace_section(text, "AIDD:PRD_OVERRIDES", _render_overrides_block(overrides))
    if updated != text:
        research_path.write_text(updated, encoding="utf-8")


def _parse_paths(value: Optional[str]) -> list[str]:
    if not value:
        return []
    items: list[str] = []
    for chunk in re.split(r"[,:]", value):
        cleaned = chunk.strip()
        if cleaned:
            items.append(cleaned)
    return items


def _parse_keywords(value: Optional[str]) -> list[str]:
    if not value:
        return []
    items: list[str] = []
    for chunk in re.split(r"[,\s]+", value):
        token = chunk.strip().lower()
        if token:
            items.append(token)
    return items


def _parse_notes(values: Optional[Iterable[str]], root: Path) -> list[str]:
    if not values:
        return []
    notes: list[str] = []
    stdin_payload: Optional[str] = None
    for raw in values:
        value = (raw or "").strip()
        if not value:
            continue
        if value == "-":
            if stdin_payload is None:
                stdin_payload = sys.stdin.read()
            payload = (stdin_payload or "").strip()
            if payload:
                notes.append(payload)
            continue
        if value.startswith("@"):
            note_path = Path(value[1:])
            if not note_path.is_absolute():
                note_path = (root / note_path).resolve()
            try:
                payload = note_path.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeDecodeError):
                continue
            if payload:
                notes.append(payload)
            continue
        notes.append(value)
    return notes


def _pack_extension() -> str:
    return ".pack.json"


def _rlm_finalize_handoff_cmd(ticket: str) -> str:
    return f"python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/aidd-rlm/runtime/rlm_finalize.py --ticket {ticket}"


def _rlm_bootstrap_cmd(ticket: str) -> str:
    return f"python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/aidd-rlm/runtime/rlm_nodes_build.py --bootstrap --ticket {ticket}"


def _jsonl_nonempty(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def _evaluate_rlm_state(
    *,
    target: Path,
    ticket: str,
    rlm_pack_path: Path,
    require_links: bool,
) -> dict[str, object]:
    nodes_path = target / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
    links_path = target / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
    links_stats_path = target / "reports" / "research" / f"{ticket}-rlm.links.stats.json"

    nodes_ready = _jsonl_nonempty(nodes_path)
    links_ok = _jsonl_nonempty(links_path)
    links_total: int | None = None
    links_empty_reason = ""
    if links_stats_path.exists():
        try:
            stats_payload = json.loads(links_stats_path.read_text(encoding="utf-8"))
        except Exception:
            stats_payload = None
        if isinstance(stats_payload, dict):
            try:
                links_total = int(stats_payload.get("links_total") or 0)
            except (TypeError, ValueError):
                links_total = None
            links_empty_reason = str(stats_payload.get("empty_reason") or "").strip()
    links_empty = links_total == 0 if links_total is not None else not links_ok
    if links_empty and not links_empty_reason:
        links_empty_reason = "no_matches"
    pack_exists = rlm_pack_path.exists()
    status = "pending"
    warnings: list[str] = []
    if pack_exists:
        if require_links and links_empty:
            status = "warn"
            warnings.append("rlm_links_empty_warn")
            if links_empty_reason:
                warnings.append(f"rlm_links_empty_reason={links_empty_reason}")
        else:
            status = "ready"
    return {
        "status": status,
        "warnings": warnings,
        "nodes_ready": nodes_ready,
        "links_ok": links_ok,
        "links_empty": links_empty,
        "links_total": links_total,
        "links_empty_reason": links_empty_reason,
        "pack_exists": pack_exists,
        "nodes_path": nodes_path,
        "links_path": links_path,
    }


def _attempt_auto_finalize(
    *,
    target: Path,
    ticket: str,
) -> dict[str, object]:
    outcome: dict[str, object] = {
        "status": "pending",
        "bootstrap_attempted": False,
        "finalize_attempted": False,
        "reason_code": "",
        "next_action": "",
        "recovery_path": "",
        "empty_reason": "",
        "details": "",
    }
    cmd = ["--ticket", ticket, "--bootstrap-if-missing", "--emit-json"]
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exit_code = int(rlm_finalize.main(cmd))
    except SystemExit as exc:
        try:
            exit_code = int(exc.code or 1)
        except (TypeError, ValueError):
            exit_code = 1
    except Exception as exc:
        outcome["reason_code"] = "rlm_finalize_failed"
        outcome["next_action"] = _rlm_finalize_handoff_cmd(ticket)
        outcome["details"] = str(exc)
        return outcome

    stdout_text = stdout_buffer.getvalue().strip()
    stderr_text = stderr_buffer.getvalue().strip()
    payload: dict[str, object] = {}
    if stdout_text:
        for line in reversed(stdout_text.splitlines()):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                payload = parsed
                break
    outcome["bootstrap_attempted"] = bool(payload.get("bootstrap_attempted"))
    outcome["finalize_attempted"] = bool(payload.get("finalize_attempted"))
    outcome["recovery_path"] = str(payload.get("recovery_path") or "").strip()
    outcome["reason_code"] = str(payload.get("reason_code") or "").strip()
    outcome["next_action"] = str(payload.get("next_action") or "").strip()
    outcome["empty_reason"] = str(payload.get("empty_reason") or "").strip()
    if exit_code == 0 and str(payload.get("status") or "").strip().lower() in {"done", "ready", "ok"}:
        outcome["status"] = "ready"
        return outcome

    outcome["status"] = "pending"
    outcome["reason_code"] = str(payload.get("reason_code") or "").strip() or "rlm_finalize_failed"
    outcome["next_action"] = str(payload.get("next_action") or "").strip() or _rlm_finalize_handoff_cmd(ticket)
    if stderr_text and not outcome["details"]:
        outcome["details"] = stderr_text
    if not outcome["reason_code"]:
        outcome["reason_code"] = "rlm_finalize_failed"
    return outcome


def _append_research_handoff(
    *,
    target: Path,
    ticket: str,
    report_path: Path,
) -> tuple[bool, str]:
    rel_report = runtime.rel_path(report_path, target)
    cmd = [
        "--source",
        "research",
        "--ticket",
        ticket,
        "--append",
        "--report",
        rel_report,
    ]
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = int(tasks_derive.main(cmd))
    except Exception as exc:
        return False, str(exc)
    return code == 0, ""


def _run_memory_extract(*, target: Path, ticket: str) -> dict[str, str]:
    outcome: dict[str, str] = {
        "status": "error",
        "reason_code": "",
        "semantic_pack": "",
        "stderr": "",
    }
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    exit_code = 1
    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exit_code = int(memory_extract.main(["--ticket", ticket, "--format", "json"]))
    except SystemExit as exc:
        try:
            exit_code = int(exc.code or 1)
        except (TypeError, ValueError):
            exit_code = 1
    except Exception as exc:
        outcome["reason_code"] = "memory_extract_failed"
        outcome["stderr"] = str(exc)
        return outcome

    stderr_text = stderr_buffer.getvalue().strip()
    if stderr_text:
        outcome["stderr"] = stderr_text

    payload: dict[str, object] = {}
    stdout_text = stdout_buffer.getvalue().strip()
    if stdout_text:
        try:
            parsed = json.loads(stdout_text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            payload = parsed
        else:
            for line in reversed(stdout_text.splitlines()):
                try:
                    parsed_line = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed_line, dict):
                    payload = parsed_line
                    break

    semantic_rel = str(payload.get("semantic_pack") or "").strip() or f"reports/memory/{ticket}.semantic.pack.json"
    semantic_path = runtime.resolve_path_for_target(Path(semantic_rel), target)
    if exit_code == 0 and semantic_path.exists():
        outcome["status"] = "ok"
        outcome["semantic_pack"] = runtime.rel_path(semantic_path, target)
        return outcome

    if exit_code != 0:
        outcome["reason_code"] = str(payload.get("reason_code") or "").strip() or "memory_extract_failed"
    elif not semantic_path.exists():
        outcome["reason_code"] = "memory_extract_missing_artifact"
    else:
        outcome["reason_code"] = str(payload.get("reason_code") or "").strip() or "memory_extract_failed"
    return outcome


def _run_memory_autoslice(*, target: Path, ticket: str) -> dict[str, Any]:
    outcome: dict[str, Any] = {
        "status": "error",
        "reason_code": "",
        "manifest_pack": "",
        "queries_ok": 0,
        "queries_total": 0,
        "stderr": "",
    }
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    exit_code = 1
    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exit_code = int(
                memory_autoslice.main(
                    [
                        "--ticket",
                        ticket,
                        "--stage",
                        "research",
                        "--scope-key",
                        runtime.resolve_scope_key("", ticket),
                        "--format",
                        "json",
                    ]
                )
            )
    except SystemExit as exc:
        try:
            exit_code = int(exc.code or 1)
        except (TypeError, ValueError):
            exit_code = 1
    except Exception as exc:
        outcome["reason_code"] = "memory_autoslice_failed"
        outcome["stderr"] = str(exc)
        return outcome

    stderr_text = stderr_buffer.getvalue().strip()
    if stderr_text:
        outcome["stderr"] = stderr_text

    payload: dict[str, Any] = {}
    stdout_text = stdout_buffer.getvalue().strip()
    if stdout_text:
        try:
            parsed = json.loads(stdout_text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            payload = parsed
        else:
            for line in reversed(stdout_text.splitlines()):
                try:
                    parsed_line = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed_line, dict):
                    payload = parsed_line
                    break
    status = str(payload.get("status") or "").strip().lower()
    outcome["status"] = status or ("ok" if exit_code == 0 else "error")
    outcome["reason_code"] = str(payload.get("reason_code") or "").strip()
    outcome["manifest_pack"] = str(payload.get("manifest_pack") or "").strip()
    outcome["queries_ok"] = int(payload.get("queries_ok") or 0)
    outcome["queries_total"] = int(payload.get("queries_total") or 0)
    if exit_code != 0 and outcome["status"] not in {"warn", "blocked"}:
        outcome["status"] = "error"
        if not outcome["reason_code"]:
            outcome["reason_code"] = "memory_autoslice_failed"
    return outcome


def _ast_next_action(ticket: str, reason_code: str) -> str:
    code = str(reason_code or "").strip().lower()
    if code == ast_index.REASON_BINARY_MISSING:
        return "Install ast-index and run `ast-index rebuild` in workspace root."
    if code == ast_index.REASON_INDEX_MISSING:
        return "Run `ast-index rebuild` in workspace root and rerun research."
    if code == ast_index.REASON_TIMEOUT:
        return f"Rerun `python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/researcher/runtime/research.py --ticket {ticket} --auto` after increasing ast_index.timeout_s."
    if code == ast_index.REASON_JSON_INVALID:
        return "Update ast-index to a version that supports `--format json` and rerun research."
    return f"python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/researcher/runtime/research.py --ticket {ticket} --auto"


def _ast_query_from_targets(
    *,
    ticket: str,
    slug_hint: str,
    targets_payload: dict[str, object],
) -> str:
    candidates: list[str] = []
    for key in ("keywords", "keywords_raw"):
        raw = targets_payload.get(key)
        if isinstance(raw, list):
            for item in raw:
                token = str(item or "").strip()
                if token:
                    candidates.append(token)
    for raw in (slug_hint, ticket):
        for chunk in re.split(r"[-_:/\s]+", str(raw or "")):
            token = chunk.strip()
            if token:
                candidates.append(token)
    seen: set[str] = set()
    for candidate in candidates:
        normalized = candidate.strip()
        key = normalized.lower()
        if len(normalized) < 2 or key in seen:
            continue
        seen.add(key)
        return normalized
    return ticket.strip() or slug_hint.strip() or "aidd"


def _rg_ast_fallback_entries(
    *,
    workspace_root: Path,
    query: str,
    max_results: int,
    target_paths: list[str],
) -> list[dict[str, object]]:
    if not query.strip():
        return []
    scan_paths: list[str] = []
    for raw in target_paths:
        token = str(raw or "").strip()
        if not token:
            continue
        candidate = Path(token)
        if not candidate.is_absolute():
            candidate = (workspace_root / candidate).resolve()
        if candidate.exists():
            scan_paths.append(str(candidate))
    cmd = [
        "rg",
        "--no-heading",
        "--line-number",
        "--column",
        "--color",
        "never",
        "--max-count",
        str(max(1, int(max_results))),
        query,
    ]
    cmd.extend(scan_paths)
    try:
        completed = subprocess.run(
            cmd,
            cwd=workspace_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except Exception:
        return []
    if completed.returncode not in {0, 1}:
        return []
    rows: list[dict[str, object]] = []
    for raw_line in (completed.stdout or "").splitlines():
        parts = raw_line.split(":", 3)
        if len(parts) < 4:
            continue
        raw_path, raw_line_no, raw_col, snippet = parts
        try:
            line_no = max(0, int(raw_line_no))
        except (TypeError, ValueError):
            line_no = 0
        try:
            column = max(0, int(raw_col))
        except (TypeError, ValueError):
            column = 0
        path_obj = Path(raw_path)
        if path_obj.is_absolute():
            try:
                normalized_path = path_obj.resolve().relative_to(workspace_root.resolve()).as_posix()
            except ValueError:
                normalized_path = path_obj.as_posix()
        else:
            normalized_path = path_obj.as_posix()
        rows.append(
            {
                "symbol": query,
                "kind": "rg_match",
                "path": normalized_path,
                "line": line_no,
                "column": column,
                "score": 0.0,
                "snippet": snippet.strip(),
            }
        )
        if len(rows) >= max(1, int(max_results)):
            break
    rows.sort(
        key=lambda row: (
            str(row.get("path") or ""),
            int(row.get("line") or 0),
            int(row.get("column") or 0),
            str(row.get("symbol") or ""),
        )
    )
    return rows


def _run_ast_retrieval(
    *,
    target: Path,
    workspace_root: Path,
    ticket: str,
    slug_hint: str,
    targets_payload: dict[str, object],
    source_path: str,
    auto_mode: bool,
) -> dict[str, Any]:
    cfg = ast_index.load_ast_index_config(target)
    outcome: dict[str, Any] = {
        "mode": cfg.mode,
        "required": bool(cfg.required),
        "status": "skipped",
        "query": "",
        "pack_path": "",
        "reason_code": "",
        "fallback_reason_code": "",
        "next_action": "",
        "matches": 0,
        "warnings": [],
        "fallback_used": False,
    }
    if not auto_mode or cfg.mode == "off":
        return outcome

    query = _ast_query_from_targets(ticket=ticket, slug_hint=slug_hint, targets_payload=targets_payload)
    outcome["query"] = query
    output_path = target / "reports" / "research" / f"{ticket}-ast.pack.json"
    target_paths = [str(item) for item in (targets_payload.get("paths") or []) if str(item).strip()]

    try:
        result = ast_index.run_json(workspace_root, cfg, ["search", query])
    except Exception as exc:
        result = ast_index.AstIndexResult(
            ok=False,
            reason_code="ast_index_runtime_error",
            fallback_reason_code=ast_index.REASON_FALLBACK_RG,
            stderr=str(exc),
        )

    if result.ok:
        entries = result.normalized or []
        reports_pack.write_ast_pack(
            entries,
            output=output_path,
            ticket=ticket,
            slug_hint=slug_hint,
            source_path=source_path,
            query=query,
            limits={"max_items": max(1, int(cfg.max_results))},
            warnings=[],
        )
        outcome["status"] = "ok"
        outcome["pack_path"] = runtime.rel_path(output_path, target)
        outcome["matches"] = len(entries)
        return outcome

    reason_code = str(result.reason_code or "ast_index_failed").strip()
    fallback_reason = str(result.fallback_reason_code or "").strip()
    warnings = [reason_code] if reason_code else []
    if fallback_reason:
        warnings.append(fallback_reason)
    outcome["reason_code"] = reason_code
    outcome["fallback_reason_code"] = fallback_reason
    outcome["warnings"] = warnings

    if cfg.required:
        outcome["status"] = "blocked"
        outcome["next_action"] = _ast_next_action(ticket, reason_code)
        return outcome

    entries: list[dict[str, object]] = []
    if cfg.allow_fallback_rg and cfg.fallback == "rg":
        entries = _rg_ast_fallback_entries(
            workspace_root=workspace_root,
            query=query,
            max_results=cfg.max_results,
            target_paths=target_paths,
        )
        outcome["fallback_used"] = True
    reports_pack.write_ast_pack(
        entries,
        output=output_path,
        ticket=ticket,
        slug_hint=slug_hint,
        source_path=source_path,
        query=query,
        limits={"max_items": max(1, int(cfg.max_results))},
        warnings=warnings,
    )
    outcome["status"] = "warn"
    outcome["pack_path"] = runtime.rel_path(output_path, target)
    outcome["matches"] = len(entries)
    return outcome


def _validate_json_file(path: Path, label: str) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"{label} invalid JSON at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} invalid JSON payload at {path}: expected object.")


def _enforce_research_artifacts(
    *,
    ticket: str,
    targets_path: Path,
    manifest_path: Path,
    worklist_path: Path,
) -> None:
    required = (
        ("rlm targets", targets_path),
        ("rlm manifest", manifest_path),
        ("rlm worklist", worklist_path),
    )
    missing = [f"{label} ({path})" for label, path in required if not path.exists()]
    if missing:
        raise RuntimeError(
            "mandatory research artifacts missing: "
            + ", ".join(missing)
            + " (reason_code=research_artifacts_missing)"
        )
    for label, path in required:
        _validate_json_file(path, label)
    try:
        targets_payload = json.loads(targets_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"rlm targets unreadable at {targets_path}: {exc}") from exc
    if str(targets_payload.get("ticket") or "").strip() and str(targets_payload.get("ticket")) != ticket:
        raise RuntimeError(
            f"rlm targets ticket mismatch at {targets_path}: expected {ticket}, got {targets_payload.get('ticket')} "
            "(reason_code=research_artifacts_invalid)"
        )
    try:
        worklist_payload = json.loads(worklist_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"rlm worklist unreadable at {worklist_path}: {exc}") from exc
    if str(worklist_payload.get("schema") or "").strip() != "aidd.report.pack.v1":
        raise RuntimeError(
            f"rlm worklist schema mismatch at {worklist_path}: expected aidd.report.pack.v1 "
            "(reason_code=research_artifacts_invalid)"
        )
    if str(worklist_payload.get("type") or "").strip().lower() != "rlm-worklist":
        raise RuntimeError(
            f"rlm worklist type mismatch at {worklist_path}: expected rlm-worklist "
            "(reason_code=research_artifacts_invalid)"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate RLM-only research artifacts for the active ticket.",
    )
    parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to analyse (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override used for templates (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--paths",
        help="Comma- or colon-separated list of explicit paths for RLM targets.",
    )
    parser.add_argument(
        "--rlm-paths",
        help="Alias for --paths when forcing explicit RLM scope.",
    )
    parser.add_argument(
        "--targets-mode",
        choices=("auto", "explicit"),
        help="Override RLM targets_mode (auto|explicit).",
    )
    parser.add_argument(
        "--keywords",
        help="Comma/space-separated extra keywords merged into RLM targets.",
    )
    parser.add_argument(
        "--note",
        dest="notes",
        action="append",
        help="Free-form note or @path merged into RLM targets notes; '-' reads stdin once.",
    )
    parser.add_argument(
        "--targets-only",
        action="store_true",
        help="Only refresh RLM targets/manifest/worklist and skip doc materialization.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated RLM targets payload without writing files.",
    )
    parser.add_argument(
        "--no-template",
        action="store_true",
        help="Do not materialise docs/research/<ticket>.md from template.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Automation-friendly mode for /feature-dev-aidd:researcher.",
    )
    # Deprecated options preserved for compatibility with old command invocations.
    parser.add_argument("--config", help=argparse.SUPPRESS)
    parser.add_argument("--paths-relative", help=argparse.SUPPRESS)
    parser.add_argument("--limit", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--output", help=argparse.SUPPRESS)
    parser.add_argument("--pack-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--deep-code", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--reuse-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--langs", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    workspace_root, target = runtime.require_workflow_root()
    ticket, feature_context = runtime.require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    write_active_state(target, ticket=ticket, stage="research")

    prd_path = target / "docs" / "prd" / f"{ticket}.prd.md"
    prd_text = prd_path.read_text(encoding="utf-8") if prd_path.exists() else ""
    prd_overrides = _extract_prd_overrides(prd_text)
    hints = prd_hints.parse_research_hints(prd_text)
    overrides_block = "\n".join(_render_overrides_block(prd_overrides))

    explicit_paths = prd_hints.merge_unique(
        _parse_paths(getattr(args, "paths", None)),
        _parse_paths(getattr(args, "rlm_paths", None)),
    )
    extra_keywords = prd_hints.merge_unique(_parse_keywords(getattr(args, "keywords", None)))
    extra_notes = prd_hints.merge_unique(_parse_notes(getattr(args, "notes", None), target))

    if not (hints.paths or hints.keywords or explicit_paths or extra_keywords):
        raise RuntimeError(
            "BLOCK: AIDD:RESEARCH_HINTS must define Paths or Keywords "
            f"in docs/prd/{ticket}.prd.md (or pass --paths/--keywords/--rlm-paths)."
        )

    settings = load_rlm_settings(target)
    targets_payload = rlm_targets.build_targets(
        target,
        ticket,
        settings=settings,
        targets_mode=args.targets_mode,
        paths_override=explicit_paths or None,
        keywords_override=extra_keywords or None,
        notes_override=extra_notes or None,
    )
    if args.dry_run:
        print(json.dumps(targets_payload, indent=2, ensure_ascii=False))
        return 0

    targets_path = target / "reports" / "research" / f"{ticket}-rlm-targets.json"
    targets_path.parent.mkdir(parents=True, exist_ok=True)
    targets_path.write_text(json.dumps(targets_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[aidd] rlm targets saved to {runtime.rel_path(targets_path, target)}.")

    manifest_payload = rlm_manifest.build_manifest(
        target,
        ticket,
        settings=settings,
        targets_path=targets_path,
    )
    manifest_path = target / "reports" / "research" / f"{ticket}-rlm-manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[aidd] rlm manifest saved to {runtime.rel_path(manifest_path, target)}.")

    nodes_path = target / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
    worklist_pack = rlm_nodes_build.build_worklist_pack(
        target,
        ticket,
        manifest_path=manifest_path,
        nodes_path=nodes_path,
    )
    worklist_path = target / "reports" / "research" / f"{ticket}-rlm.worklist{_pack_extension()}"
    worklist_path.write_text(
        json.dumps(worklist_pack, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"[aidd] rlm worklist saved to {runtime.rel_path(worklist_path, target)}.")
    try:
        _enforce_research_artifacts(
            ticket=ticket,
            targets_path=targets_path,
            manifest_path=manifest_path,
            worklist_path=worklist_path,
        )
    except RuntimeError as exc:
        print(f"[aidd] ERROR: {exc}", file=sys.stderr)
        return 2

    links_path = target / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
    rlm_pack_rel = f"reports/research/{ticket}-rlm{_pack_extension()}"
    rlm_pack_path = target / rlm_pack_rel
    if nodes_path.exists() and links_path.exists() and nodes_path.stat().st_size > 0 and links_path.stat().st_size > 0:
        try:
            from aidd_runtime import reports_pack as _reports_pack

            rlm_pack_path = _reports_pack.write_rlm_pack(
                nodes_path,
                links_path,
                ticket=ticket,
                slug_hint=feature_context.slug_hint,
                root=target,
                limits=None,
            )
            _validate_json_file(rlm_pack_path, "rlm pack")
            print(f"[aidd] rlm pack saved to {runtime.rel_path(rlm_pack_path, target)}.")
        except Exception as exc:
            print(f"[aidd] ERROR: failed to generate rlm pack: {exc}", file=sys.stderr)
            return 2

    gates_cfg = runtime.load_gates_config(target)
    rlm_cfg = gates_cfg.get("rlm") if isinstance(gates_cfg, dict) else {}
    require_links = bool(rlm_cfg.get("require_links")) if isinstance(rlm_cfg, dict) else False
    state = _evaluate_rlm_state(
        target=target,
        ticket=ticket,
        rlm_pack_path=rlm_pack_path,
        require_links=require_links,
    )
    rlm_status = str(state["status"])
    rlm_warnings: list[str] = list(state["warnings"])
    nodes_ready = bool(state["nodes_ready"])
    links_ok = bool(state["links_ok"])
    pack_exists = bool(state["pack_exists"])
    links_empty = bool(state["links_empty"])
    links_empty_reason = str(state.get("links_empty_reason") or "").strip()

    if args.targets_only:
        runtime.maybe_sync_index(target, ticket, feature_context.slug_hint, reason="research-targets")
        return 0

    finalize_outcome: dict[str, object] = {
        "status": "pending",
        "bootstrap_attempted": False,
        "finalize_attempted": False,
        "reason_code": "",
        "next_action": "",
        "recovery_path": "",
        "details": "",
    }
    if args.auto and rlm_status != "ready":
        finalize_outcome = _attempt_auto_finalize(target=target, ticket=ticket)
        if str(finalize_outcome.get("status") or "").strip().lower() == "ready":
            state = _evaluate_rlm_state(
                target=target,
                ticket=ticket,
                rlm_pack_path=rlm_pack_path,
                require_links=require_links,
            )
            rlm_status = str(state["status"])
            rlm_warnings = list(state["warnings"])
            nodes_ready = bool(state["nodes_ready"])
            links_ok = bool(state["links_ok"])
            pack_exists = bool(state["pack_exists"])
            links_empty = bool(state["links_empty"])
            links_empty_reason = str(state.get("links_empty_reason") or "").strip()
            if rlm_status == "ready":
                print("[aidd] INFO: rlm finalize auto-recovery succeeded.", file=sys.stderr)
        else:
            reason_code = str(finalize_outcome.get("reason_code") or "").strip()
            if reason_code and reason_code not in rlm_warnings:
                rlm_warnings.append(reason_code)
            empty_reason = str(finalize_outcome.get("empty_reason") or "").strip()
            if empty_reason:
                links_empty_reason = empty_reason
                reason_marker = f"rlm_links_empty_reason={empty_reason}"
                if reason_marker not in rlm_warnings:
                    rlm_warnings.append(reason_marker)

    pending_reason_code = ""
    pending_next_action = ""
    baseline_marker = "none"
    if rlm_status != "ready":
        finalized_reason = str(finalize_outcome.get("reason_code") or "").strip()
        finalized_next = str(finalize_outcome.get("next_action") or "").strip()
        if links_empty and require_links and not finalized_reason:
            pending_reason_code = "rlm_links_empty_warn"
            pending_next_action = (
                f"python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/aidd-rlm/runtime/rlm_links_build.py --ticket {ticket}"
            )
        elif finalized_reason:
            pending_reason_code = finalized_reason
            pending_next_action = finalized_next or _rlm_finalize_handoff_cmd(ticket)
        elif not nodes_ready and not links_ok and not pack_exists:
            pending_reason_code = "baseline_pending"
            pending_next_action = _rlm_bootstrap_cmd(ticket)
        elif not nodes_ready:
            pending_reason_code = "rlm_nodes_missing"
            pending_next_action = _rlm_bootstrap_cmd(ticket)
        elif not links_ok or not pack_exists:
            pending_reason_code = "finalize_prereqs_missing"
            pending_next_action = _rlm_finalize_handoff_cmd(ticket)
        else:
            pending_reason_code = "rlm_status_pending"
            pending_next_action = _rlm_finalize_handoff_cmd(ticket)
        if pending_reason_code == "baseline_pending":
            baseline_marker = "Контекст пуст: требуется baseline после автоматического запуска."
        elif links_empty and links_empty_reason:
            baseline_marker = f"links_empty_reason={links_empty_reason}"

    ast_source_rel = runtime.rel_path(rlm_pack_path if pack_exists else worklist_path, target)
    ast_outcome = _run_ast_retrieval(
        target=target,
        workspace_root=workspace_root,
        ticket=ticket,
        slug_hint=feature_context.slug_hint or ticket,
        targets_payload=targets_payload,
        source_path=ast_source_rel,
        auto_mode=bool(args.auto),
    )
    ast_status = str(ast_outcome.get("status") or "skipped")
    ast_pack_path = str(ast_outcome.get("pack_path") or "").strip()
    ast_reason_code = str(ast_outcome.get("reason_code") or "").strip()
    ast_fallback_reason_code = str(ast_outcome.get("fallback_reason_code") or "").strip()
    ast_next_action = str(ast_outcome.get("next_action") or "").strip()
    ast_matches = int(ast_outcome.get("matches") or 0)
    ast_query = str(ast_outcome.get("query") or "").strip()
    if ast_pack_path:
        print(f"[aidd] ast pack saved to {ast_pack_path}.")
    if ast_status == "warn":
        reason_label = ast_reason_code or "ast_index_fallback"
        print(
            "[aidd] WARN: ast-index degraded to rg fallback "
            f"(reason_code={reason_label}).",
            file=sys.stderr,
        )
    if ast_status == "blocked":
        reason_label = ast_reason_code or "ast_index_required"
        print(
            "[aidd] ERROR: ast-index required but not ready "
            f"(reason_code={reason_label}).",
            file=sys.stderr,
        )
        if ast_next_action:
            print(f"[aidd] ERROR: next_action: `{ast_next_action}`.", file=sys.stderr)
        return 2

    if not args.no_template:
        template_overrides = {
            "{{doc_status}}": _doc_status_from_rlm(rlm_status),
            "{{prd_overrides}}": overrides_block,
            "{{paths}}": ",".join(targets_payload.get("paths") or []) or "TBD",
            "{{keywords}}": ",".join(targets_payload.get("keywords") or []) or "TBD",
            "{{paths_discovered}}": ", ".join(targets_payload.get("paths_discovered") or []) or "none",
            "{{invalid_paths}}": "none",
            "{{rlm_status}}": rlm_status,
            "{{rlm_pack_path}}": runtime.rel_path(rlm_pack_path, target) if pack_exists else rlm_pack_rel,
            "{{rlm_pack_status}}": "found" if pack_exists else "missing",
            "{{rlm_pack_bytes}}": str(rlm_pack_path.stat().st_size) if pack_exists else "0",
            "{{rlm_pack_updated_at}}": (
                dt.datetime.fromtimestamp(rlm_pack_path.stat().st_mtime, tz=dt.timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z")
                if pack_exists
                else ""
            ),
            "{{rlm_warnings}}": ", ".join(rlm_warnings) if rlm_warnings else "none",
            "{{rlm_nodes_path}}": runtime.rel_path(nodes_path, target),
            "{{rlm_links_path}}": runtime.rel_path(links_path, target),
            "{{rlm_pending_reason}}": pending_reason_code or "none",
            "{{rlm_next_action}}": pending_next_action or "none",
            "{{rlm_baseline_marker}}": baseline_marker,
            "{{rlm_bootstrap_attempted}}": "yes" if finalize_outcome.get("bootstrap_attempted") else "no",
            "{{rlm_finalize_attempted}}": "yes" if finalize_outcome.get("finalize_attempted") else "no",
            "{{rlm_recovery_path}}": str(finalize_outcome.get("recovery_path") or "none"),
            "{{ast_mode}}": str(ast_outcome.get("mode") or "off"),
            "{{ast_required}}": "yes" if bool(ast_outcome.get("required")) else "no",
            "{{ast_status}}": ast_status,
            "{{ast_query}}": ast_query or "none",
            "{{ast_pack_path}}": ast_pack_path or f"reports/research/{ticket}-ast.pack.json",
            "{{ast_matches}}": str(ast_matches),
            "{{ast_reason_code}}": ast_reason_code or "none",
            "{{ast_fallback_reason}}": ast_fallback_reason_code or "none",
            "{{ast_next_action}}": ast_next_action or "none",
        }
        doc_path, created = _ensure_research_doc(
            target,
            ticket,
            slug_hint=feature_context.slug_hint,
            template_overrides=template_overrides,
        )
        if not doc_path:
            print("[aidd] research summary template not found; skipping materialisation.")
        else:
            rel_doc = doc_path.relative_to(target).as_posix()
            if created == "created":
                print(f"[aidd] research summary created at {rel_doc}.")
            elif created == "updated":
                print(f"[aidd] research summary refreshed at {rel_doc}.")
            else:
                print(f"[aidd] research summary already up-to-date at {rel_doc}.")

    _sync_prd_overrides(target, ticket=ticket, overrides=prd_overrides)

    memory_status = "skipped"
    memory_semantic_pack = ""
    memory_reason_code = ""
    memory_slice_status = "skipped"
    memory_slice_reason_code = ""
    memory_slice_manifest_pack = ""
    if rlm_status == "ready":
        memory_outcome = _run_memory_extract(target=target, ticket=ticket)
        memory_status = str(memory_outcome.get("status") or "error")
        memory_semantic_pack = str(memory_outcome.get("semantic_pack") or "").strip()
        memory_reason_code = str(memory_outcome.get("reason_code") or "").strip()
        if memory_status != "ok":
            stderr_note = str(memory_outcome.get("stderr") or "").strip()
            reason_label = memory_reason_code or "memory_extract_failed"
            print(
                "[aidd] ERROR: failed to generate memory semantic pack "
                f"(reason_code={reason_label}).",
                file=sys.stderr,
            )
            if stderr_note:
                print(f"[aidd] ERROR: {stderr_note}", file=sys.stderr)
            return 2
        print(f"[aidd] memory semantic pack saved to {memory_semantic_pack}.")
        autoslice_outcome = _run_memory_autoslice(target=target, ticket=ticket)
        memory_slice_status = str(autoslice_outcome.get("status") or "error")
        memory_slice_reason_code = str(autoslice_outcome.get("reason_code") or "").strip()
        memory_slice_manifest_pack = str(autoslice_outcome.get("manifest_pack") or "").strip()
        if memory_slice_status == "blocked":
            reason_label = memory_slice_reason_code or "memory_slice_missing"
            print(
                "[aidd] ERROR: memory autoslice blocked research stage "
                f"(reason_code={reason_label}).",
                file=sys.stderr,
            )
            return 2
        if memory_slice_status == "warn":
            reason_label = memory_slice_reason_code or "memory_slice_missing_warn"
            print(
                "[aidd] WARN: memory autoslice degraded "
                f"(reason_code={reason_label}).",
                file=sys.stderr,
            )
        elif memory_slice_status != "ok":
            reason_label = memory_slice_reason_code or "memory_autoslice_failed"
            print(
                "[aidd] WARN: failed to materialize memory autoslice "
                f"(reason_code={reason_label}).",
                file=sys.stderr,
            )
        elif memory_slice_manifest_pack:
            print(f"[aidd] memory slice manifest saved to {memory_slice_manifest_pack}.")
    else:
        memory_reason_code = "rlm_not_ready"

    handoff_appended = False
    handoff_error = ""
    if rlm_status != "ready":
        handoff_report = rlm_pack_path if pack_exists else worklist_path
        handoff_appended, handoff_error = _append_research_handoff(
            target=target,
            ticket=ticket,
            report_path=handoff_report,
        )
        if handoff_error:
            print(
                f"[aidd] WARN: failed to append research handoff task ({handoff_error}).",
                file=sys.stderr,
            )
        reason_label = pending_reason_code or "rlm_status_pending"
        next_action = pending_next_action or _rlm_finalize_handoff_cmd(ticket)
        if baseline_marker != "none":
            print(f"[aidd] INFO: {baseline_marker}", file=sys.stderr)
        print(
            "[aidd] INFO: shared RLM API owner is `aidd-rlm`; "
            f"reason_code={reason_label}; next_action: `{next_action}`.",
            file=sys.stderr,
        )

    try:
        from aidd_runtime.reports import events as _events

        report_rel = memory_semantic_pack or ast_pack_path or runtime.rel_path(rlm_pack_path if pack_exists else worklist_path, target)
        _events.append_event(
            target,
            ticket=ticket,
            slug_hint=feature_context.slug_hint,
            event_type="research",
            status="ok" if rlm_status == "ready" else "pending",
            details={
                "rlm_status": rlm_status,
                "worklist_entries": len(worklist_pack.get("entries") or []),
                "pending_reason_code": pending_reason_code or None,
                "pending_next_action": pending_next_action or None,
                "bootstrap_attempted": bool(finalize_outcome.get("bootstrap_attempted")),
                "finalize_attempted": bool(finalize_outcome.get("finalize_attempted")),
                "recovery_path": str(finalize_outcome.get("recovery_path") or "") or None,
                "handoff_appended": handoff_appended,
                "handoff_error": handoff_error or None,
                "memory_status": memory_status,
                "memory_semantic_pack": memory_semantic_pack or None,
                "memory_reason_code": memory_reason_code or None,
                "memory_slice_status": memory_slice_status,
                "memory_slice_reason_code": memory_slice_reason_code or None,
                "memory_slice_manifest_pack": memory_slice_manifest_pack or None,
                "ast_mode": str(ast_outcome.get("mode") or ""),
                "ast_required": bool(ast_outcome.get("required")),
                "ast_status": ast_status,
                "ast_pack_path": ast_pack_path or None,
                "ast_query": ast_query or None,
                "ast_matches": ast_matches,
                "ast_reason_code": ast_reason_code or None,
                "ast_fallback_reason_code": ast_fallback_reason_code or None,
                "ast_next_action": ast_next_action or None,
                "ast_fallback_used": bool(ast_outcome.get("fallback_used")),
            },
            report_path=Path(report_rel),
            source="aidd research",
        )
    except Exception:
        pass

    research_pack_reads = 0
    if pack_exists:
        research_pack_reads += 1
    elif worklist_path.exists():
        research_pack_reads += 1
    if ast_pack_path:
        research_pack_reads += 1
    if memory_semantic_pack:
        research_pack_reads += 1
    if memory_slice_manifest_pack:
        research_pack_reads += 1

    try:
        context_quality.update_from_ast(
            target,
            ticket=ticket,
            ast_mode=str(ast_outcome.get("mode") or ""),
            ast_status=ast_status,
            ast_reason_codes=[
                ast_reason_code,
                ast_fallback_reason_code,
            ],
            ast_fallback_used=bool(ast_outcome.get("fallback_used")),
            pack_reads=research_pack_reads,
            full_reads=0,
        )
    except Exception:
        pass

    runtime.maybe_sync_index(target, ticket, feature_context.slug_hint, reason="research")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

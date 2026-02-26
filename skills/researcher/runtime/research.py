from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Iterable, Optional

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(_PLUGIN_ROOT))
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from aidd_runtime import research_hints as prd_hints
from aidd_runtime import rlm_finalize, rlm_manifest, rlm_nodes_build, rlm_targets, runtime, tasks_derive
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
    for heading in ("AIDD:CONTEXT_PACK", "AIDD:PRD_OVERRIDES", "AIDD:RLM_EVIDENCE"):
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
    _, target = runtime.require_workflow_root()
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

    if not args.no_template:
        auto_recovery_attempted = bool(
            finalize_outcome.get("bootstrap_attempted") or finalize_outcome.get("finalize_attempted")
        )
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
            "{{rlm_auto_recovery_attempted}}": "yes" if auto_recovery_attempted else "no",
            "{{rlm_bootstrap_attempted}}": "yes" if finalize_outcome.get("bootstrap_attempted") else "no",
            "{{rlm_finalize_attempted}}": "yes" if finalize_outcome.get("finalize_attempted") else "no",
            "{{rlm_recovery_path}}": str(finalize_outcome.get("recovery_path") or "none"),
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
            },
            report_path=Path(runtime.rel_path(rlm_pack_path if pack_exists else worklist_path, target)),
            source="aidd research",
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

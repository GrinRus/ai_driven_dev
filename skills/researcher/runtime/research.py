from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable, Optional

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("CLAUDE_PLUGIN_ROOT", str(_PLUGIN_ROOT))
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from aidd_runtime import research_hints as prd_hints
from aidd_runtime import rlm_manifest, rlm_nodes_build, rlm_targets, runtime
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


def _validate_json_file(path: Path, label: str) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"{label} invalid JSON at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} invalid JSON payload at {path}: expected object.")


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

    links_ok = links_path.exists() and links_path.stat().st_size > 0
    pack_exists = rlm_pack_path.exists()
    rlm_status = "pending"
    rlm_warnings: list[str] = []
    gates_cfg = runtime.load_gates_config(target)
    rlm_cfg = gates_cfg.get("rlm") if isinstance(gates_cfg, dict) else {}
    require_links = bool(rlm_cfg.get("require_links")) if isinstance(rlm_cfg, dict) else False
    links_total = None
    links_stats_path = target / "reports" / "research" / f"{ticket}-rlm.links.stats.json"
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
    links_empty = links_total == 0 if links_total is not None else not links_ok
    if pack_exists:
        if require_links and links_empty:
            rlm_status = "warn"
            rlm_warnings.append("rlm_links_empty_warn")
            print("[aidd] WARN: rlm links empty; rlm_status set to warn.", file=sys.stderr)
        else:
            rlm_status = "ready"

    if args.targets_only:
        runtime.maybe_sync_index(target, ticket, feature_context.slug_hint, reason="research-targets")
        return 0

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

    if rlm_status != "ready":
        print(
            "[aidd] INFO: shared RLM API owner is `aidd-rlm`; "
            f"handoff command: `{_rlm_finalize_handoff_cmd(ticket)}`.",
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

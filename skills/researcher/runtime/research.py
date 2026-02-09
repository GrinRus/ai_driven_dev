from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

from aidd_runtime import runtime
from aidd_runtime.researcher_context import (
    ResearcherContextBuilder,
    _parse_keywords as _research_parse_keywords,
    _parse_langs as _research_parse_langs,
    _parse_notes as _research_parse_notes,
    _parse_paths as _research_parse_paths,
)


def _ensure_research_doc(
    target: Path,
    ticket: str,
    slug_hint: Optional[str],
    *,
    template_overrides: Optional[dict[str, str]] = None,
) -> tuple[Optional[Path], bool]:
    template = target / "docs" / "research" / "template.md"
    destination = target / "docs" / "research" / f"{ticket}.md"
    if not template.exists():
        return None, False
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return destination, False
    content = template.read_text(encoding="utf-8")
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
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    destination.write_text(content, encoding="utf-8")
    return destination, True


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


def _validate_json_file(path: Path, label: str) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"{label} invalid JSON at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} invalid JSON payload at {path}: expected object.")


def _pack_extension() -> str:
    return ".pack.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect scope and context for the Researcher agent.",
    )
    parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to analyse (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override used for templates and keywords (defaults to docs/.active.json).",
    )
    parser.add_argument(
        "--config",
        help="Path to conventions JSON containing the researcher section (defaults to config/conventions.json).",
    )
    parser.add_argument(
        "--paths",
        help="Colon-separated list of additional paths to scan (overrides defaults from conventions).",
    )
    parser.add_argument(
        "--rlm-paths",
        help="Comma- or colon-separated list of explicit paths for RLM targets (overrides auto-discovery).",
    )
    parser.add_argument(
        "--targets-mode",
        choices=("auto", "explicit"),
        help="Override RLM targets_mode (auto|explicit).",
    )
    parser.add_argument(
        "--paths-relative",
        choices=("workspace", "aidd"),
        help="Treat relative paths as workspace-rooted (default) or under aidd/.",
    )
    parser.add_argument(
        "--keywords",
        help="Comma-separated list of extra keywords to search for.",
    )
    parser.add_argument(
        "--note",
        dest="notes",
        action="append",
        help="Free-form note or @path to include in the context; use '-' to read stdin once.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=24,
        help="Maximum number of code/document matches to capture (default: 24).",
    )
    parser.add_argument(
        "--output",
        help="Override output JSON path (default: aidd/reports/research/<ticket>-context.json).",
    )
    parser.add_argument(
        "--pack-only",
        action="store_true",
        help="Remove JSON report after writing pack sidecar.",
    )
    parser.add_argument(
        "--targets-only",
        action="store_true",
        help="Only refresh targets JSON; skip content scan and context export.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print context JSON to stdout without writing files (targets are still refreshed).",
    )
    parser.add_argument(
        "--deep-code",
        action="store_true",
        help="Collect code symbols/imports/tests for reuse candidates.",
    )
    parser.add_argument(
        "--reuse-only",
        action="store_true",
        help="Skip keyword matches and focus on reuse candidates in the output.",
    )
    parser.add_argument(
        "--langs",
        help="Comma-separated list of languages to scan for deep analysis (py,kt,kts,java).",
    )
    parser.add_argument(
        "--no-template",
        action="store_true",
        help="Do not materialise docs/research/<ticket>.md from the template.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Automation-friendly mode for /feature-dev-aidd:idea-new integrations (warn on empty matches).",
    )
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
    overrides_block = "\n".join(_render_overrides_block(prd_overrides))

    def _sync_index(reason: str) -> None:
        runtime.maybe_sync_index(target, ticket, feature_context.slug_hint, reason=reason)

    config_path: Optional[Path] = None
    if args.config:
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = (target / config_path).resolve()
        else:
            config_path = config_path.resolve()
    builder = ResearcherContextBuilder(
        target,
        config_path=config_path,
        paths_relative=getattr(args, "paths_relative", None),
    )
    scope = builder.build_scope(ticket, slug_hint=feature_context.slug_hint)
    extra_paths = _research_parse_paths(args.paths)
    rlm_paths = _research_parse_paths(getattr(args, "rlm_paths", None))
    if rlm_paths and not extra_paths:
        scope = builder.sync_scope_paths(scope, rlm_paths)
        print("[aidd] INFO: research paths synced to --rlm-paths scope.", file=sys.stderr)
    scope = builder.extend_scope(
        scope,
        extra_paths=extra_paths,
        extra_keywords=_research_parse_keywords(args.keywords),
        extra_notes=_research_parse_notes(getattr(args, "notes", None), target),
    )
    _, _, search_roots = builder.describe_targets(scope)
    path_roots = builder.resolve_path_roots(scope)
    if scope.invalid_paths and not scope.paths_discovered:
        missing = ", ".join(scope.invalid_paths[:6])
        suffix = "..." if len(scope.invalid_paths) > 6 else ""
        print(
            f"[aidd] WARN: missing research paths: {missing}{suffix} "
            "(use --paths-relative workspace or update conventions)",
            file=sys.stderr,
        )

    targets_path = builder.write_targets(scope)
    rel_targets = targets_path.relative_to(target).as_posix()
    base_root = builder.workspace_root if builder.paths_relative_mode == "workspace" else builder.root
    base_label = f"{builder.paths_relative_mode}:{base_root}"
    print(
        f"[aidd] researcher targets saved to {rel_targets} "
        f"({len(scope.paths)} paths, {len(scope.docs)} docs; base={base_label})."
    )

    rlm_targets_path = None
    rlm_manifest_path = None
    rlm_worklist_path = None
    pack_ext = _pack_extension()
    try:
        rlm_targets_path = builder.write_rlm_targets(
            ticket,
            targets_mode=args.targets_mode,
            rlm_paths=rlm_paths,
        )
        from aidd_runtime import rlm_manifest, rlm_nodes_build
        from aidd_runtime.rlm_config import load_rlm_settings

        rlm_settings = load_rlm_settings(target)
        manifest_payload = rlm_manifest.build_manifest(
            target,
            ticket,
            settings=rlm_settings,
            targets_path=rlm_targets_path,
        )
        rlm_manifest_path = target / "reports" / "research" / f"{ticket}-rlm-manifest.json"
        rlm_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        rlm_manifest_path.write_text(
            json.dumps(manifest_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        worklist_pack = rlm_nodes_build.build_worklist_pack(
            target,
            ticket,
            manifest_path=rlm_manifest_path,
            nodes_path=target / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl",
        )
        worklist_name = f"{ticket}-rlm.worklist{pack_ext}"
        rlm_worklist_path = target / "reports" / "research" / worklist_name
        rlm_worklist_path.parent.mkdir(parents=True, exist_ok=True)
        rlm_worklist_path.write_text(
            json.dumps(worklist_pack, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[aidd] WARN: failed to generate rlm targets/manifest/worklist: {exc}", file=sys.stderr)

    if args.targets_only:
        if not getattr(args, "dry_run", False):
            _sync_index("research-targets")
        return 0

    languages = _research_parse_langs(getattr(args, "langs", None))
    deep_code_enabled = bool(args.deep_code)
    if args.auto:
        auto_profile = "deep-scan" if deep_code_enabled else "fast-scan"
        auto_reason = "explicit --deep-code" if deep_code_enabled else "no --deep-code"
        print(f"[aidd] researcher auto profile: {auto_profile} ({auto_reason}).")

    collected_context = builder.collect_context(scope, limit=args.limit)
    if deep_code_enabled:
        code_index, reuse_candidates = builder.collect_deep_context(
            scope,
            roots=search_roots,
            keywords=scope.keywords,
            languages=languages,
            reuse_only=args.reuse_only,
            limit=args.limit,
        )
        collected_context["code_index"] = code_index
        collected_context["reuse_candidates"] = reuse_candidates
        collected_context["deep_mode"] = True
    else:
        collected_context["deep_mode"] = False

    collected_context["auto_mode"] = bool(getattr(args, "auto", False))
    if rlm_targets_path:
        collected_context["rlm_targets_path"] = os.path.relpath(rlm_targets_path, target)
    if rlm_manifest_path:
        collected_context["rlm_manifest_path"] = os.path.relpath(rlm_manifest_path, target)
    if rlm_worklist_path:
        collected_context["rlm_worklist_path"] = os.path.relpath(rlm_worklist_path, target)
    nodes_path = target / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
    links_path = target / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
    rlm_pack_rel = f"reports/research/{ticket}-rlm{pack_ext}"
    rlm_pack_path = target / rlm_pack_rel
    if not args.dry_run:
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
                try:
                    _validate_json_file(rlm_pack_path, "rlm pack")
                except RuntimeError as exc:
                    print(f"[aidd] ERROR: {exc}", file=sys.stderr)
                    return 2
                rel_rlm_pack = rlm_pack_path.relative_to(target).as_posix()
                print(f"[aidd] rlm pack saved to {rel_rlm_pack}.")
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
    links_empty = False
    if links_total is not None:
        links_empty = links_total == 0
    else:
        links_empty = not links_ok
    if pack_exists:
        if require_links and links_empty:
            rlm_status = "warn"
            rlm_warnings.append("rlm_links_empty_warn")
            print("[aidd] WARN: rlm links empty; rlm_status set to warn.", file=sys.stderr)
        else:
            rlm_status = "ready"

    collected_context["rlm_nodes_path"] = nodes_path.relative_to(target).as_posix()
    collected_context["rlm_links_path"] = links_path.relative_to(target).as_posix()
    collected_context["rlm_pack_path"] = rlm_pack_rel
    if links_stats_path.exists():
        collected_context["rlm_links_stats_path"] = links_stats_path.relative_to(target).as_posix()
    collected_context["rlm_status"] = rlm_status
    collected_context["rlm_pack_status"] = "found" if pack_exists else "missing"
    if pack_exists:
        stat = rlm_pack_path.stat()
        collected_context["rlm_pack_bytes"] = stat.st_size
        collected_context["rlm_pack_updated_at"] = (
            dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
    if rlm_warnings:
        collected_context["rlm_warnings"] = rlm_warnings
    match_count = len(collected_context["matches"])
    if match_count == 0:
        print(
            f"[aidd] WARN: 0 matches for `{ticket}` → сузить paths/keywords.",
            file=sys.stderr,
        )
        if (
            builder.paths_relative_mode == "aidd"
            and builder.workspace_root != builder.root
            and any((builder.workspace_root / name).exists() for name in ("src", "services", "modules", "apps"))
        ):
            print(
                "[aidd] hint: включите workspace-relative paths (--paths-relative workspace) "
                "или добавьте ../paths — под aidd/ нет поддерживаемых файлов, но в workspace есть код.",
                file=sys.stderr,
            )
    if args.dry_run:
        print(json.dumps(collected_context, indent=2, ensure_ascii=False))
        return 0

    output = Path(args.output) if args.output else None
    output_path = builder.write_context(scope, collected_context, output=output)
    try:
        _validate_json_file(output_path, "research context")
    except RuntimeError as exc:
        print(f"[aidd] ERROR: {exc}", file=sys.stderr)
        return 2
    rel_output = output_path.relative_to(target).as_posix()
    pack_path = None
    try:
        from aidd_runtime import reports_pack as _reports_pack

        pack_path = _reports_pack.write_research_context_pack(output_path, root=target)
        try:
            _validate_json_file(pack_path, "research pack")
        except RuntimeError as exc:
            print(f"[aidd] ERROR: {exc}", file=sys.stderr)
            return 2
        try:
            rel_pack = pack_path.relative_to(target).as_posix()
        except ValueError:
            rel_pack = pack_path.as_posix()
        print(f"[aidd] research pack saved to {rel_pack}.")
    except Exception as exc:
        print(f"[aidd] ERROR: failed to generate research pack: {exc}", file=sys.stderr)
        return 2
    reuse_count = len(collected_context.get("reuse_candidates") or []) if deep_code_enabled else 0
    message = f"[aidd] researcher context saved to {rel_output} ({match_count} matches; base={base_label}"
    if deep_code_enabled:
        message += f", {reuse_count} reuse candidates"
    message += ")."
    print(message)

    if not args.no_template:
        template_overrides: dict[str, str] = {}
        if overrides_block:
            template_overrides["{{prd_overrides}}"] = overrides_block
        if match_count == 0:
            template_overrides["{{empty-context-note}}"] = "Контекст пуст: требуется baseline после автоматического запуска."
            template_overrides["{{positive-patterns}}"] = "TBD — данные появятся после baseline."
            template_overrides["{{negative-patterns}}"] = "TBD — сначала найдите артефакты."
        if scope.manual_notes:
            template_overrides["{{manual-note}}"] = "; ".join(scope.manual_notes[:3])

        doc_path, created = _ensure_research_doc(
            target,
            ticket,
            slug_hint=feature_context.slug_hint,
            template_overrides=template_overrides or None,
        )
        if not doc_path:
            print("[aidd] research summary template not found; skipping materialisation.")
        else:
            rel_doc = doc_path.relative_to(target).as_posix()
            if created:
                print(f"[aidd] research summary created at {rel_doc}.")
            else:
                print(f"[aidd] research summary already exists at {rel_doc}.")

    _sync_prd_overrides(target, ticket=ticket, overrides=prd_overrides)

    try:
        from aidd_runtime.reports import events as _events

        _events.append_event(
            target,
            ticket=ticket,
            slug_hint=feature_context.slug_hint,
            event_type="research",
            status="empty" if match_count == 0 else "ok",
            details={
                "matches": match_count,
                "reuse_candidates": reuse_count,
            },
            report_path=Path(rel_output),
            source="aidd research",
        )
    except Exception:
        pass

    pack_only = bool(getattr(args, "pack_only", False) or os.getenv("AIDD_PACK_ONLY", "").strip() == "1")
    if pack_only and pack_path and pack_path.exists():
        try:
            output_path.unlink()
        except OSError:
            pass
    _sync_index("research")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

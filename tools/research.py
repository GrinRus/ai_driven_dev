from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Optional

from tools import runtime
from tools.researcher_context import (
    ResearcherContextBuilder,
    _CALLGRAPH_LANGS,
    _columnar_call_graph,
    _DEFAULT_GRAPH_LIMIT,
    _emit_call_graph_warning,
    _parse_graph_engine as _research_parse_graph_engine,
    _parse_graph_filter as _research_parse_graph_filter,
    _parse_graph_mode as _research_parse_graph_mode,
    _parse_keywords as _research_parse_keywords,
    _parse_langs as _research_parse_langs,
    _parse_notes as _research_parse_notes,
    _parse_paths as _research_parse_paths,
    _select_graph_edges,
    _strip_trim_warning,
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect scope and context for the Researcher agent.",
    )
    parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to analyse (defaults to docs/.active_ticket).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override used for templates and keywords (defaults to docs/.active_feature).",
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
        help="Collect code symbols/imports/tests for reuse candidates (enables call graph unless --graph-engine none).",
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
        "--call-graph",
        action="store_true",
        help=(
            "Build call/import graph (tree-sitter when available). Deprecated: graph is built automatically in deep-code "
            "unless --graph-engine none; use --graph-mode to control focus/full."
        ),
    )
    parser.add_argument(
        "--graph-engine",
        choices=["auto", "none", "ts"],
        default="auto",
        help="Engine for call graph: auto (tree-sitter when available), none (disable), ts (force tree-sitter).",
    )
    parser.add_argument(
        "--graph-langs",
        help="Comma-separated list of languages for call graph (kt,kts,java; others ignored).",
    )
    parser.add_argument(
        "--graph-filter",
        help="Regex to keep only matching call graph edges (matches file/caller/callee). Defaults to ticket/keywords.",
    )
    parser.add_argument(
        "--graph-limit",
        type=int,
        default=_DEFAULT_GRAPH_LIMIT,
        help=f"Maximum number of call graph edges to keep in focused graph (default: {_DEFAULT_GRAPH_LIMIT}).",
    )
    parser.add_argument(
        "--graph-mode",
        choices=["auto", "focus", "full"],
        default="auto",
        help="Graph selection for context: auto (full if small), focus (filter+limit), full (no filter/limit).",
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
    scope = builder.extend_scope(
        scope,
        extra_paths=_research_parse_paths(args.paths),
        extra_keywords=_research_parse_keywords(args.keywords),
        extra_notes=_research_parse_notes(getattr(args, "notes", None), target),
    )
    _, _, search_roots = builder.describe_targets(scope)

    targets_path = builder.write_targets(scope)
    rel_targets = targets_path.relative_to(target).as_posix()
    base_root = builder.workspace_root if builder.paths_relative_mode == "workspace" else builder.root
    base_label = f"{builder.paths_relative_mode}:{base_root}"
    print(
        f"[aidd] researcher targets saved to {rel_targets} "
        f"({len(scope.paths)} paths, {len(scope.docs)} docs; base={base_label})."
    )

    if args.targets_only:
        if not getattr(args, "dry_run", False):
            _sync_index("research-targets")
        return 0

    languages = _research_parse_langs(getattr(args, "langs", None))
    graph_languages = _research_parse_langs(getattr(args, "graph_langs", None))
    graph_engine = _research_parse_graph_engine(getattr(args, "graph_engine", None))
    graph_mode = _research_parse_graph_mode(getattr(args, "graph_mode", None))
    auto_filter = "|".join(scope.keywords + [scope.ticket])
    graph_filter = _research_parse_graph_filter(getattr(args, "graph_filter", None), fallback=auto_filter)
    raw_limit = getattr(args, "graph_limit", _DEFAULT_GRAPH_LIMIT)
    try:
        graph_limit = int(raw_limit)
    except (TypeError, ValueError):
        graph_limit = _DEFAULT_GRAPH_LIMIT
    if graph_limit <= 0:
        graph_limit = _DEFAULT_GRAPH_LIMIT

    deep_code_enabled = bool(args.deep_code)
    call_graph_requested = bool(args.call_graph)
    if args.auto:
        if deep_code_enabled or call_graph_requested:
            auto_profile = "graph-scan"
            auto_reason = "explicit flags"
        else:
            callgraph_files = builder._iter_callgraph_files(search_roots, list(_CALLGRAPH_LANGS))
            if callgraph_files:
                auto_profile = "graph-scan"
                auto_reason = "kt/kts/java detected"
                deep_code_enabled = True
                call_graph_requested = True
            else:
                auto_profile = "fast-scan"
                auto_reason = "no kt/kts/java detected"
                deep_code_enabled = False
                call_graph_requested = False
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
    graph_enabled = graph_engine != "none"
    should_build_graph = graph_enabled and (call_graph_requested or deep_code_enabled)
    collected_context["call_graph"] = []
    collected_context["import_graph"] = []
    collected_context["call_graph_engine"] = graph_engine
    collected_context["call_graph_supported_languages"] = []
    collected_context["call_graph_filter"] = graph_filter
    collected_context["call_graph_limit"] = graph_limit
    collected_context["call_graph_warning"] = ""
    if should_build_graph:
        graph = builder.collect_call_graph(
            scope,
            roots=search_roots,
            languages=graph_languages or languages or list(_CALLGRAPH_LANGS),
            engine_name=graph_engine,
            graph_filter=graph_filter,
            graph_limit=graph_limit,
        )
        selected_edges, selected_mode = _select_graph_edges(graph, graph_mode, graph_limit)
        collected_context["call_graph"] = selected_edges
        collected_context["import_graph"] = graph.get("imports", [])
        collected_context["call_graph_engine"] = graph.get("engine", graph_engine)
        collected_context["call_graph_supported_languages"] = graph.get("supported_languages", [])
        warning = graph.get("warning") or ""
        if selected_mode == "full":
            warning = _strip_trim_warning(warning)
        collected_context["call_graph_warning"] = warning
        _emit_call_graph_warning("[aidd]", warning)

        full_edges = graph.get("edges_full")
        if full_edges is None:
            full_edges = graph.get("edges") or []
        full_path = Path(args.output or f"aidd/reports/research/{ticket}-call-graph-full.json")
        full_path = runtime.resolve_path_for_target(full_path, target)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_payload = {"edges": full_edges, "imports": graph.get("imports", [])}
        full_path.write_text(json.dumps(full_payload, indent=2), encoding="utf-8")
        collected_context["call_graph_full_path"] = os.path.relpath(full_path, target)
        columnar_path = full_path.with_suffix(".cjson")
        try:
            columnar_payload = _columnar_call_graph(
                full_payload.get("edges", []),
                full_payload.get("imports", []),
            )
            columnar_path.write_text(json.dumps(columnar_payload, indent=2), encoding="utf-8")
            collected_context["call_graph_full_columnar_path"] = os.path.relpath(columnar_path, target)
        except OSError:
            pass
    elif graph_engine == "none" and (call_graph_requested or deep_code_enabled):
        collected_context["call_graph_warning"] = "call graph disabled (graph-engine none)"
    collected_context["auto_mode"] = bool(getattr(args, "auto", False))
    match_count = len(collected_context["matches"])
    if match_count == 0:
        print(
            f"[aidd] WARN: 0 matches for `{ticket}` → сузить paths/keywords или graph-only.",
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
    rel_output = output_path.relative_to(target).as_posix()
    pack_path = None
    try:
        from tools import reports_pack as _reports_pack

        pack_path = _reports_pack.write_research_context_pack(output_path, root=target)
        try:
            rel_pack = pack_path.relative_to(target).as_posix()
        except ValueError:
            rel_pack = pack_path.as_posix()
        print(f"[aidd] research pack saved to {rel_pack}.")
    except Exception as exc:
        print(f"[aidd] WARN: failed to generate research pack: {exc}", file=sys.stderr)
    reuse_count = len(collected_context.get("reuse_candidates") or []) if deep_code_enabled else 0
    call_edges = len(collected_context.get("call_graph") or []) if should_build_graph else 0
    message = f"[aidd] researcher context saved to {rel_output} ({match_count} matches; base={base_label}"
    if deep_code_enabled:
        message += f", {reuse_count} reuse candidates"
    if should_build_graph:
        message += f", {call_edges} call edges"
    message += ")."
    print(message)

    if not args.no_template:
        template_overrides: dict[str, str] = {}
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

    try:
        from tools.reports import events as _events

        _events.append_event(
            target,
            ticket=ticket,
            slug_hint=feature_context.slug_hint,
            event_type="research",
            status="empty" if match_count == 0 else "ok",
            details={
                "matches": match_count,
                "reuse_candidates": reuse_count,
                "call_graph_edges": call_edges,
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

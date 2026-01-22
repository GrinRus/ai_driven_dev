from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

from tools import runtime
from tools.researcher_context import (
    ResearcherContextBuilder,
    _CALLGRAPH_LANGS,
    _DEFAULT_GRAPH_LIMIT,
    _emit_call_graph_warning,
    _parse_graph_engine as _research_parse_graph_engine,
    _parse_graph_mode as _research_parse_graph_mode,
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


def _validate_json_file(path: Path, label: str) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"{label} invalid JSON at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} invalid JSON payload at {path}: expected object.")


def _unique_tokens(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _build_call_graph_filter(
    scope,
    builder: ResearcherContextBuilder,
    explicit_filter: Optional[str],
) -> tuple[str, dict[str, int | str], bool]:
    if explicit_filter:
        return explicit_filter.strip(), {"source": "explicit", "tokens_raw": 0, "tokens_used": 0}, False
    settings = builder.call_graph_settings()
    max_tokens = int(settings.get("filter_max_tokens", 20))
    max_chars = int(settings.get("filter_max_chars", 512))

    tokens = _unique_tokens([scope.ticket] + list(scope.keywords))
    raw_tokens = list(tokens)
    trimmed = False
    if max_tokens > 0 and len(tokens) > max_tokens:
        tokens = tokens[:max_tokens]
        trimmed = True

    parts: list[str] = []
    for token in tokens:
        escaped = re.escape(token)
        if max_chars > 0:
            candidate = "|".join(parts + [escaped]) if parts else escaped
            if len(candidate) > max_chars:
                trimmed = True
                break
        parts.append(escaped)

    if not parts and scope.ticket:
        parts = [re.escape(scope.ticket)]
        trimmed = trimmed or len(raw_tokens) > 1
    filter_regex = "|".join(parts)

    stats = {
        "source": "auto",
        "tokens_raw": len(raw_tokens),
        "tokens_used": len(parts),
        "max_tokens": max_tokens,
        "max_chars": max_chars,
        "chars": len(filter_regex),
    }
    return filter_regex, stats, trimmed


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
        help=(
            f"Maximum number of call graph edges when call_graph.edges_max is unset "
            f"(default: {_DEFAULT_GRAPH_LIMIT})."
        ),
    )
    parser.add_argument(
        "--graph-mode",
        choices=["auto", "focus", "full"],
        default="auto",
        help="Graph selection for context: auto (focus unless full), focus (filter+limit), full (no filter).",
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
    path_roots = builder.resolve_path_roots(scope)
    if scope.invalid_paths:
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

    if args.targets_only:
        if not getattr(args, "dry_run", False):
            _sync_index("research-targets")
        return 0

    languages = _research_parse_langs(getattr(args, "langs", None))
    graph_languages = _research_parse_langs(getattr(args, "graph_langs", None))
    graph_engine = _research_parse_graph_engine(getattr(args, "graph_engine", None))
    graph_mode = _research_parse_graph_mode(getattr(args, "graph_mode", None))
    explicit_filter = getattr(args, "graph_filter", None)
    if explicit_filter is not None and not str(explicit_filter).strip():
        explicit_filter = None
    graph_filter, filter_stats, filter_trimmed = _build_call_graph_filter(scope, builder, explicit_filter)
    graph_settings = builder.call_graph_settings()
    try:
        edges_max = int(graph_settings.get("edges_max", 0))
    except (TypeError, ValueError):
        edges_max = 0
    raw_limit = getattr(args, "graph_limit", _DEFAULT_GRAPH_LIMIT)
    try:
        graph_limit = int(raw_limit)
    except (TypeError, ValueError):
        graph_limit = _DEFAULT_GRAPH_LIMIT
    if graph_limit <= 0:
        graph_limit = _DEFAULT_GRAPH_LIMIT
    edges_limit = edges_max if edges_max and edges_max > 0 else graph_limit
    filter_for_edges = None if graph_mode == "full" else graph_filter

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
    collected_context["import_graph"] = []
    collected_context["call_graph_engine"] = graph_engine
    collected_context["call_graph_supported_languages"] = []
    collected_context["call_graph_filter"] = filter_for_edges
    collected_context["call_graph_limit"] = edges_limit
    collected_context["filter_stats"] = filter_stats
    collected_context["filter_trimmed"] = filter_trimmed
    collected_context["call_graph_warning"] = ""
    if should_build_graph:
        graph = builder.collect_call_graph(
            scope,
            roots=search_roots,
            languages=graph_languages or languages or list(_CALLGRAPH_LANGS),
            engine_name=graph_engine,
            graph_filter=filter_for_edges,
            edges_max=edges_limit,
        )
        edge_stream = graph.get("edges_stream")
        if edge_stream is None:
            edge_stream = []
        collected_context["import_graph"] = graph.get("imports", [])
        collected_context["call_graph_engine"] = graph.get("engine", graph_engine)
        collected_context["call_graph_supported_languages"] = graph.get("supported_languages", [])
        warning = graph.get("warning") or ""
        _emit_call_graph_warning("[aidd]", warning)
        try:
            from tools import call_graph_views

            edges_path = Path(f"aidd/reports/research/{ticket}-call-graph.edges.jsonl")
            edges_path = runtime.resolve_path_for_target(edges_path, target)
            edges_written, _ = call_graph_views.write_edges_jsonl(edge_stream, edges_path)
            truncated = bool(getattr(edge_stream, "truncated", False))
            if truncated:
                suffix = f"call graph truncated to {edges_written} edges."
                warning = f"{warning} {suffix}".strip()
            collected_context["call_graph_edges_path"] = os.path.relpath(edges_path, target)
            collected_context["call_graph_edges_schema"] = call_graph_views.EDGE_SCHEMA
            collected_context["call_graph_edges_stats"] = {
                "edges_scanned": getattr(edge_stream, "edges_scanned", edges_written),
                "edges_written": edges_written,
                "edges_limit": edges_limit,
            }
            collected_context["call_graph_edges_truncated"] = truncated
        except OSError:
            pass
        collected_context["call_graph_warning"] = warning
    elif graph_engine == "none" and (call_graph_requested or deep_code_enabled):
        collected_context["call_graph_warning"] = "call graph disabled (graph-engine none)"

    ast_grep_stats = None
    try:
        from tools.ast_grep_scan import scan_ast_grep

        ast_output = Path(f"aidd/reports/research/{ticket}-ast-grep.jsonl")
        ast_output = runtime.resolve_path_for_target(ast_output, target)
        ast_path, ast_grep_stats = scan_ast_grep(
            target,
            ticket=ticket,
            search_roots=path_roots,
            output=ast_output,
            tags=scope.tags,
        )
        if ast_path:
            collected_context["ast_grep_path"] = os.path.relpath(ast_path, target)
            collected_context["ast_grep_schema"] = ast_grep_stats.get("schema") if ast_grep_stats else None
            collected_context["ast_grep_stats"] = ast_grep_stats
        else:
            if ast_grep_stats:
                collected_context["ast_grep_stats"] = ast_grep_stats
            if ast_grep_stats and ast_grep_stats.get("reason") not in {"disabled", "langs-not-required"}:
                reason = ast_grep_stats.get("reason")
                if reason == "binary-missing":
                    print("[aidd] INSTALL_HINT: install ast-grep (https://ast-grep.github.io/)", file=sys.stderr)
                if reason == "scan-failed":
                    detail = ast_grep_stats.get("error") or ast_grep_stats.get("stderr")
                    detail_suffix = f": {detail}" if detail else ""
                    print(f"[aidd] WARN: ast-grep scan failed{detail_suffix}.", file=sys.stderr)
                else:
                    print(f"[aidd] WARN: ast-grep scan skipped ({reason}).", file=sys.stderr)
    except Exception:
        pass
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
    try:
        _validate_json_file(output_path, "research context")
    except RuntimeError as exc:
        print(f"[aidd] ERROR: {exc}", file=sys.stderr)
        return 2
    rel_output = output_path.relative_to(target).as_posix()
    pack_path = None
    try:
        from tools import reports_pack as _reports_pack

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
    if call_graph_requested or deep_code_enabled:
        try:
            graph_pack_path = _reports_pack.write_call_graph_pack(output_path, root=target)
            try:
                _validate_json_file(graph_pack_path, "call-graph pack")
            except RuntimeError as exc:
                print(f"[aidd] ERROR: {exc}", file=sys.stderr)
                return 2
            try:
                rel_graph_pack = graph_pack_path.relative_to(target).as_posix()
            except ValueError:
                rel_graph_pack = graph_pack_path.as_posix()
            print(f"[aidd] call-graph pack saved to {rel_graph_pack}.")
        except Exception as exc:
            print(f"[aidd] ERROR: failed to generate call-graph pack: {exc}", file=sys.stderr)
            return 2
    ast_grep_path = collected_context.get("ast_grep_path")
    if ast_grep_path:
        try:
            abs_ast_grep_path = target / ast_grep_path
            ast_pack_path = _reports_pack.write_ast_grep_pack(
                abs_ast_grep_path,
                ticket=ticket,
                slug_hint=feature_context.slug_hint,
                stats=collected_context.get("ast_grep_stats"),
                root=target,
            )
            try:
                _validate_json_file(ast_pack_path, "ast-grep pack")
            except RuntimeError as exc:
                print(f"[aidd] ERROR: {exc}", file=sys.stderr)
                return 2
            try:
                rel_ast_pack = ast_pack_path.relative_to(target).as_posix()
            except ValueError:
                rel_ast_pack = ast_pack_path.as_posix()
            print(f"[aidd] ast-grep pack saved to {rel_ast_pack}.")
        except Exception as exc:
            print(f"[aidd] ERROR: failed to generate ast-grep pack: {exc}", file=sys.stderr)
            return 2
    reuse_count = len(collected_context.get("reuse_candidates") or []) if deep_code_enabled else 0
    call_edges = 0
    if should_build_graph:
        call_edges = (collected_context.get("call_graph_edges_stats") or {}).get("edges_written") or 0
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

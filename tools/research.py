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


def _pack_extension() -> str:
    return ".pack.json"


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
        "--evidence-engine",
        choices=("rlm", "auto"),
        default="auto",
        help="Evidence engine to use (auto defaults to rlm).",
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
        from tools import rlm_manifest, rlm_nodes_build
        from tools.rlm_config import load_rlm_settings

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
    evidence_engine = str(getattr(args, "evidence_engine", "auto")).strip().lower()

    deep_code_enabled = bool(args.deep_code)
    if args.auto and evidence_engine != "rlm":
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

    ast_grep_stats = None
    if evidence_engine == "rlm":
        collected_context["ast_grep_stats"] = {"reason": "rlm-disabled"}
    else:
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
                if ast_grep_stats:
                    reason = ast_grep_stats.get("reason")
                    if reason in {"disabled", "langs-not-required"}:
                        if reason == "disabled":
                            detail = (
                                " (set aidd/config/conventions.json: "
                                "researcher.ast_grep.enabled=true or required_for_langs=[...])"
                            )
                        else:
                            detail = " (adjust researcher.ast_grep.required_for_langs if needed)"
                        print(f"[aidd] INFO: ast-grep scan skipped ({reason}){detail}.", file=sys.stderr)
                    elif reason == "binary-missing":
                        print("[aidd] INSTALL_HINT: install ast-grep (https://ast-grep.github.io/)", file=sys.stderr)
                    elif reason == "scan-failed":
                        detail = ast_grep_stats.get("error") or ast_grep_stats.get("stderr")
                        detail_suffix = f": {detail}" if detail else ""
                        print(f"[aidd] WARN: ast-grep scan failed{detail_suffix}.", file=sys.stderr)
                    else:
                        print(f"[aidd] WARN: ast-grep scan skipped ({reason}).", file=sys.stderr)
        except Exception as exc:
            collected_context["ast_grep_stats"] = {"reason": "exception", "error": f"{type(exc).__name__}: {exc}"}
            print(
                f"[aidd] WARN: ast-grep scan errored: {type(exc).__name__}: {exc}.",
                file=sys.stderr,
            )
    collected_context["auto_mode"] = bool(getattr(args, "auto", False))
    if rlm_targets_path:
        collected_context["rlm_targets_path"] = os.path.relpath(rlm_targets_path, target)
    if rlm_manifest_path:
        collected_context["rlm_manifest_path"] = os.path.relpath(rlm_manifest_path, target)
    if rlm_worklist_path:
        collected_context["rlm_worklist_path"] = os.path.relpath(rlm_worklist_path, target)
    collected_context["rlm_nodes_path"] = f"reports/research/{ticket}-rlm.nodes.jsonl"
    collected_context["rlm_links_path"] = f"reports/research/{ticket}-rlm.links.jsonl"
    collected_context["rlm_pack_path"] = f"reports/research/{ticket}-rlm{pack_ext}"
    collected_context["rlm_status"] = "pending"
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
    rlm_pack_path = None
    nodes_path = target / "reports" / "research" / f"{ticket}-rlm.nodes.jsonl"
    links_path = target / "reports" / "research" / f"{ticket}-rlm.links.jsonl"
    if nodes_path.exists() and links_path.exists() and nodes_path.stat().st_size > 0 and links_path.stat().st_size > 0:
        try:
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
    message = f"[aidd] researcher context saved to {rel_output} ({match_count} matches; base={base_label}"
    if deep_code_enabled:
        message += f", {reuse_count} reuse candidates"
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

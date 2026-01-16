from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import os
import shlex
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from aidd_runtime.feature_ids import (
    FeatureIdentifiers,
    read_identifiers,
    resolve_identifiers,
    resolve_project_root as resolve_aidd_root,
    write_identifiers,
)

from aidd_runtime import progress as _progress
from aidd_runtime.tools.analyst_guard import (
    AnalystValidationError,
    load_settings as _load_analyst_settings,
    validate_prd as _validate_analyst_prd,
)
from aidd_runtime.tools.research_guard import (
    ResearchValidationError,
    load_settings as _load_research_settings,
    validate_research as _validate_research,
)
from aidd_runtime.tools.researcher_context import (
    ResearcherContextBuilder,
    _DEFAULT_GRAPH_LIMIT,
    _parse_keywords as _research_parse_keywords,
    _parse_langs as _research_parse_langs,
    _parse_graph_engine as _research_parse_graph_engine,
    _parse_graph_filter as _research_parse_graph_filter,
    _parse_notes as _research_parse_notes,
    _parse_paths as _research_parse_paths,
)
from aidd_runtime.tools import plan_review_gate as _plan_review_gate
from aidd_runtime.tools import prd_review as _prd_review
from aidd_runtime.tools import prd_review_gate as _prd_review_gate
from aidd_runtime.tools import qa_agent as _qa_agent
from aidd_runtime.tools import tasklist_check as _tasklist_check
from aidd_runtime.context_gc import (
    precompact_snapshot as _context_precompact,
    pretooluse_guard as _context_pretooluse,
    sessionstart_inject as _context_sessionstart,
    stop_update as _context_stop,
    userprompt_guard as _context_userprompt,
)
from aidd_runtime.resources import (
    DEFAULT_PROJECT_SUBDIR,
    resolve_project_root as resolve_workspace_root,
)


try:
    VERSION = metadata.version("aidd-runtime")
except metadata.PackageNotFoundError:  # pragma: no cover - editable installs
    VERSION = "0.1.0"

DEFAULT_REVIEWER_MARKER = "aidd/reports/reviewer/{ticket}.json"
DEFAULT_REVIEW_REPORT = "aidd/reports/reviewer/{ticket}.json"
DEFAULT_REVIEWER_FIELD = "tests"
DEFAULT_REVIEWER_REQUIRED = ("required",)
DEFAULT_REVIEWER_OPTIONAL = ("optional", "skipped", "not-required")
def _default_qa_test_command() -> list[list[str]]:
    plugin_root = Path(os.getenv("CLAUDE_PLUGIN_ROOT", ".")).resolve()
    return [["bash", str(plugin_root / "hooks" / "format-and-test.sh")]]
WORKSPACE_ROOT_DIRS = {".claude", ".claude-plugin"}
VALID_STAGES = {
    "idea",
    "research",
    "plan",
    "review-plan",
    "review-prd",
    "spec-interview",
    "tasklist",
    "implement",
    "review",
    "qa",
}


def _resolve_roots(raw_target: Path, *, create: bool = False) -> tuple[Path, Path]:
    workspace_root, project_root = resolve_workspace_root(raw_target, DEFAULT_PROJECT_SUBDIR)
    if project_root.exists():
        return workspace_root, project_root
    if create:
        project_root.mkdir(parents=True, exist_ok=True)
        return workspace_root, project_root
    if not workspace_root.exists():
        raise FileNotFoundError(f"workspace directory {workspace_root} does not exist")
    plugin_root = os.getenv("CLAUDE_PLUGIN_ROOT", ".")
    raise FileNotFoundError(
        f"workflow not found at {project_root}. Run '/aidd-init' or "
        f"'PYTHONPATH={plugin_root} python3 -m aidd_runtime.cli init --target {workspace_root}' "
        f"(templates install into ./{DEFAULT_PROJECT_SUBDIR})."
    )


def _require_workflow_root(raw_target: Path) -> tuple[Path, Path]:
    workspace_root, project_root = _resolve_roots(raw_target, create=False)
    if (project_root / "docs").exists():
        return workspace_root, project_root
    plugin_root = os.getenv("CLAUDE_PLUGIN_ROOT", ".")
    raise FileNotFoundError(
        f"workflow files not found at {project_root}/docs; "
        f"bootstrap via '/aidd-init' or "
        f"'PYTHONPATH={plugin_root} python3 -m aidd_runtime.cli init --target {workspace_root}' "
        f"(templates install into ./{DEFAULT_PROJECT_SUBDIR})."
    )


def _normalize_stage(value: str) -> str:
    return value.strip().lower().replace(" ", "-")

def _run_subprocess(
    cmd: List[str], *, cwd: Path, env: dict[str, str] | None = None
) -> int:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    try:
        subprocess.run(cmd, cwd=str(cwd), env=run_env, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"failed to execute {cmd[0]}: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"command {' '.join(cmd)} exited with code {exc.returncode};"
            " see logs above for details"
        ) from exc
    return 0


def _copy_tree(src: Path, dest: Path, *, force: bool) -> list[Path]:
    copied: list[Path] = []
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        target = dest / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if target.exists() and not force:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(target)
    return copied


def _run_init(
    target: Path,
    extra_args: List[str] | None = None,
) -> None:
    extra_args = extra_args or []
    workspace_root, project_root = _resolve_roots(target, create=True)
    current_version = _read_template_version(project_root)
    if current_version and current_version != VERSION:
        print(
            f"[aidd] existing template version {current_version} detected;"
            f" CLI {VERSION} will refresh files."
        )

    force = "--force" in extra_args
    ignored = [arg for arg in extra_args if arg != "--force"]
    if ignored:
        print(f"[aidd] init flags ignored in marketplace-only mode: {' '.join(ignored)}")

    plugin_root = Path(os.getenv("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[1])).resolve()
    templates_root = plugin_root / "templates" / DEFAULT_PROJECT_SUBDIR
    if not templates_root.exists():
        raise FileNotFoundError(
            f"templates not found at {templates_root}. "
            "Run '/aidd-init' from the plugin repository."
        )

    project_root.mkdir(parents=True, exist_ok=True)
    copied = _copy_tree(templates_root, project_root, force=force)
    if copied:
        print(f"[aidd:init] copied {len(copied)} files into {project_root}")
    else:
        print(f"[aidd:init] no changes (already initialized) in {project_root}")
    _write_template_version(project_root)


def _run_smoke(verbose: bool) -> None:
    plugin_root = Path(os.getenv("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[1])).resolve()
    script = plugin_root / "dev" / "repo_tools" / "smoke-workflow.sh"
    if not script.exists():
        raise FileNotFoundError(f"smoke script not found at {script}")
    cmd = ["bash", str(script)]
    env = {}
    if verbose:
        env["SMOKE_VERBOSE"] = "1"
    _run_subprocess(cmd, cwd=plugin_root, env=env)


def _init_command(args: argparse.Namespace) -> None:
    script_args = ["--commit-mode", args.commit_mode]
    if args.enable_ci:
        script_args.append("--enable-ci")
    if args.force:
        script_args.append("--force")
    if args.dry_run:
        script_args.append("--dry-run")
    _run_init(Path(args.target).resolve(), script_args)


def _smoke_command(args: argparse.Namespace) -> None:
    _run_smoke(args.verbose)


def _set_active_stage_command(args: argparse.Namespace) -> int:
    root = resolve_aidd_root(Path(args.target))
    stage = _normalize_stage(args.stage)
    if not args.allow_custom and stage not in VALID_STAGES:
        valid = ", ".join(sorted(VALID_STAGES))
        print(f"[stage] invalid stage '{stage}'. Allowed: {valid}.", file=sys.stderr)
        return 2
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    stage_path = docs_dir / ".active_stage"
    stage_path.write_text(stage + "\n", encoding="utf-8")
    print(f"active stage: {stage}")
    context = _resolve_feature_context(root)
    _maybe_sync_index(root, context.resolved_ticket, context.slug_hint, reason="set-active-stage")
    return 0


def _set_active_feature_command(args: argparse.Namespace) -> int:
    root = resolve_aidd_root(Path(args.target))
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    write_identifiers(
        root,
        ticket=args.ticket,
        slug_hint=args.slug_note,
        scaffold_prd_file=not args.skip_prd_scaffold,
    )
    identifiers = read_identifiers(root)
    resolved_slug_hint = identifiers.slug_hint or identifiers.ticket or args.ticket

    print(f"active feature: {args.ticket}")

    config_path: Optional[Path] = None
    if args.config:
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = (root / config_path).resolve()
        else:
            config_path = config_path.resolve()

    builder = ResearcherContextBuilder(root, config_path=config_path)
    scope = builder.build_scope(args.ticket, slug_hint=resolved_slug_hint)
    scope = builder.extend_scope(
        scope,
        extra_paths=_research_parse_paths(args.paths),
        extra_keywords=_research_parse_keywords(args.keywords),
    )
    targets_path = builder.write_targets(scope)
    rel_targets = targets_path.relative_to(root).as_posix()
    print(f"[researcher] targets saved to {rel_targets} ({len(scope.paths)} paths, {len(scope.docs)} docs)")

    index_ticket = identifiers.resolved_ticket or args.ticket
    index_slug = resolved_slug_hint or index_ticket
    _maybe_sync_index(
        root,
        index_ticket,
        index_slug,
        reason="set-active-feature",
        announce=True,
    )
    return 0


def _identifiers_command(args: argparse.Namespace) -> int:
    root = resolve_aidd_root(Path(args.target))
    identifiers = resolve_identifiers(root, ticket=args.ticket, slug_hint=args.slug_hint)
    if args.json:
        payload = {
            "ticket": identifiers.ticket,
            "slug_hint": identifiers.slug_hint,
            "resolved_ticket": identifiers.resolved_ticket,
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    ticket = identifiers.resolved_ticket or ""
    hint = (identifiers.slug_hint or "").strip()
    if hint and hint != ticket:
        if ticket:
            print(f"{ticket} ({hint})")
        else:
            print(hint)
    else:
        print(ticket)
    return 0


def _prd_review_command(args: argparse.Namespace) -> int:
    _, target = _require_workflow_root(Path(args.target).resolve())
    exit_code = _prd_review.run(args)
    if exit_code == 0:
        context = _resolve_feature_context(
            target,
            ticket=getattr(args, "ticket", None),
            slug_hint=getattr(args, "slug_hint", None),
        )
        ticket = (context.resolved_ticket or "").strip()
        slug_hint = (context.slug_hint or ticket).strip() or ticket
        _maybe_sync_index(target, ticket, slug_hint, reason="prd-review")
    return exit_code


def _plan_review_gate_command(args: argparse.Namespace) -> int:
    return _plan_review_gate.run_gate(args)


def _prd_review_gate_command(args: argparse.Namespace) -> int:
    return _prd_review_gate.run_gate(args)


def _researcher_context_command(args: argparse.Namespace) -> int:
    from aidd_runtime.tools import researcher_context as _researcher_context

    argv = args.forward_args or []
    if argv and argv[0] == "--":
        argv = argv[1:]
    return _researcher_context.main(argv)


def _context_gc_command(args: argparse.Namespace) -> None:
    mode = args.mode
    if mode == "precompact":
        _context_precompact.main()
    elif mode == "sessionstart":
        _context_sessionstart.main()
    elif mode == "pretooluse":
        _context_pretooluse.main()
    elif mode == "stop":
        _context_stop.main()
    elif mode == "userprompt":
        _context_userprompt.main()


def _analyst_check_command(args: argparse.Namespace) -> None:
    _, target = _require_workflow_root(Path(args.target).resolve())
    ticket, context = _require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    settings = _load_analyst_settings(target)
    try:
        summary = _validate_analyst_prd(
            target,
            ticket,
            settings=settings,
            branch=args.branch,
            require_ready_override=False if args.no_ready_required else None,
            allow_blocked_override=True if args.allow_blocked else None,
            min_questions_override=args.min_questions,
        )
    except AnalystValidationError as exc:
        raise RuntimeError(str(exc)) from exc

    if summary.status is None:
        print("[aidd] analyst gate disabled; nothing to validate.")
        return

    label = _format_ticket_label(context, fallback=ticket)
    print(f"[aidd] analyst dialog ready for `{label}` "
          f"(status: {summary.status}, questions: {summary.question_count}).")


def _research_check_command(args: argparse.Namespace) -> None:
    _, target = _require_workflow_root(Path(args.target).resolve())
    ticket, context = _require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    settings = _load_research_settings(target)
    try:
        summary = _validate_research(
            target,
            ticket,
            settings=settings,
            branch=args.branch,
        )
    except ResearchValidationError as exc:
        raise RuntimeError(str(exc)) from exc

    if summary.status is None:
        if summary.skipped_reason:
            print(f"[aidd] research gate skipped ({summary.skipped_reason}).")
        else:
            print("[aidd] research gate disabled; nothing to validate.")
        return

    label = _format_ticket_label(context, fallback=ticket)
    details = [f"status: {summary.status}"]
    if summary.path_count is not None:
        details.append(f"paths: {summary.path_count}")
    if summary.age_days is not None:
        details.append(f"age: {summary.age_days}d")
    print(f"[aidd] research gate OK for `{label}` ({', '.join(details)}).")


def _tasklist_check_command(args: argparse.Namespace) -> int:
    return _tasklist_check.run_check(args)


def _research_command(args: argparse.Namespace) -> None:
    _, target = _require_workflow_root(Path(args.target).resolve())

    ticket, feature_context = _require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )

    def _sync_index(reason: str) -> None:
        _maybe_sync_index(target, ticket, feature_context.slug_hint, reason=reason)

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
        return

    languages = _research_parse_langs(getattr(args, "langs", None))
    graph_languages = _research_parse_langs(getattr(args, "graph_langs", None))
    graph_engine = _research_parse_graph_engine(getattr(args, "graph_engine", None))
    auto_filter = "|".join(scope.keywords + [scope.ticket])
    graph_filter = _research_parse_graph_filter(getattr(args, "graph_filter", None), fallback=auto_filter)
    raw_limit = getattr(args, "graph_limit", _DEFAULT_GRAPH_LIMIT)
    try:
        graph_limit = int(raw_limit)
    except (TypeError, ValueError):
        graph_limit = _DEFAULT_GRAPH_LIMIT
    if graph_limit <= 0:
        graph_limit = _DEFAULT_GRAPH_LIMIT

    collected_context = builder.collect_context(scope, limit=args.limit)
    if args.deep_code:
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
    if args.call_graph:
        graph = builder.collect_call_graph(
            scope,
            roots=search_roots,
            languages=graph_languages or languages or ["kt", "kts", "java"],
            engine_name=graph_engine,
            graph_filter=graph_filter,
            graph_limit=graph_limit,
        )
        collected_context["call_graph"] = graph.get("edges", [])
        collected_context["import_graph"] = graph.get("imports", [])
        collected_context["call_graph_engine"] = graph.get("engine", graph_engine)
        collected_context["call_graph_supported_languages"] = graph.get("supported_languages", [])
        if graph.get("edges_full") is not None:
            full_path = Path(args.output or f"aidd/reports/research/{ticket}-call-graph-full.json")
            full_path = _resolve_path_for_target(full_path, target)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_payload = {"edges": graph.get("edges_full", []), "imports": graph.get("imports", [])}
            full_path.write_text(json.dumps(full_payload, indent=2), encoding="utf-8")
            collected_context["call_graph_full_path"] = os.path.relpath(full_path, target)
        collected_context["call_graph_filter"] = graph_filter
        collected_context["call_graph_limit"] = graph_limit
        if graph.get("warning"):
            collected_context["call_graph_warning"] = graph.get("warning")
    else:
        collected_context["call_graph"] = []
        collected_context["import_graph"] = []
        collected_context["call_graph_engine"] = graph_engine
        collected_context["call_graph_supported_languages"] = []
    collected_context["auto_mode"] = bool(getattr(args, "auto", False))
    match_count = len(collected_context["matches"])
    if match_count == 0:
        print(
            f"[aidd] researcher found 0 matches for `{ticket}` — зафиксируйте baseline и статус pending в docs/research/{ticket}.md."
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
        return

    output = Path(args.output) if args.output else None
    output_path = builder.write_context(scope, collected_context, output=output)
    rel_output = output_path.relative_to(target).as_posix()
    pack_path = None
    try:
        from aidd_runtime.tools import reports_pack as _reports_pack

        pack_path = _reports_pack.write_research_context_pack(output_path, root=target)
        try:
            rel_pack = pack_path.relative_to(target).as_posix()
        except ValueError:
            rel_pack = pack_path.as_posix()
        print(f"[aidd] research pack saved to {rel_pack}.")
    except Exception as exc:
        print(f"[aidd] WARN: failed to generate research pack: {exc}", file=sys.stderr)
    reuse_count = len(collected_context.get("reuse_candidates") or []) if args.deep_code else 0
    call_edges = len(collected_context.get("call_graph") or []) if args.call_graph else 0
    message = f"[aidd] researcher context saved to {rel_output} ({match_count} matches; base={base_label}"
    if args.deep_code:
        message += f", {reuse_count} reuse candidates"
    if args.call_graph:
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


def _index_sync_command(args: argparse.Namespace) -> int:
    _, target = _require_workflow_root(Path(args.target).resolve())
    ticket, context = _require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    slug = (getattr(args, "slug", None) or context.slug_hint or ticket).strip()
    from aidd_runtime.tools import index_sync as _index_sync

    output = Path(args.output) if args.output else None
    index_path = _index_sync.write_index(target, ticket, slug, output=output)
    rel = _rel_path(index_path, target)
    print(f"[aidd] index saved to {rel}.")
    return 0


def _context_pack_command(args: argparse.Namespace) -> int:
    _, target = _require_workflow_root(Path(args.target).resolve())
    ticket, context = _require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    agent = (args.agent or "").strip()
    if not agent:
        raise ValueError("agent name is required (use --agent <name>)")
    output = Path(args.output) if args.output else None
    from aidd_runtime.tools import context_pack as _context_pack

    pack_path = _context_pack.write_context_pack(
        target,
        ticket=ticket,
        agent=agent,
        output=output,
    )
    rel = _rel_path(pack_path, target)
    print(f"[aidd] context pack saved to {rel}.")
    return 0


def _status_command(args: argparse.Namespace) -> int:
    _, target = _require_workflow_root(Path(args.target).resolve())
    ticket, context = _require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    slug = context.slug_hint or ticket

    from aidd_runtime.tools import index_sync as _index_sync
    from aidd_runtime.reports import events as _events
    from aidd_runtime.reports import tests_log as _tests_log

    index_path = target / "docs" / "index" / f"{ticket}.yaml"
    if args.refresh or not index_path.exists():
        _index_sync.write_index(target, ticket, slug)

    try:
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        index_payload = {}

    stage = index_payload.get("stage") or ""
    summary = index_payload.get("summary") or ""
    print(f"[status] {ticket}" + (f" (stage: {stage})" if stage else ""))
    if summary:
        print(f"- Summary: {summary}")
    updated = index_payload.get("updated")
    if updated:
        print(f"- Updated: {updated}")
    artifacts = index_payload.get("artifacts") or []
    if artifacts:
        print("- Artifacts:")
        for item in artifacts:
            print(f"  - {item}")
    reports = index_payload.get("reports") or []
    if reports:
        print("- Reports:")
        for item in reports:
            print(f"  - {item}")
    next3 = index_payload.get("next3") or []
    if next3:
        print("- AIDD:NEXT_3:")
        for item in next3:
            print(f"  - {item}")
    open_questions = index_payload.get("open_questions") or []
    if open_questions:
        print("- Open questions:")
        for item in open_questions:
            print(f"  - {item}")
    risks = index_payload.get("risks_top5") or []
    if risks:
        print("- Risks:")
        for item in risks:
            print(f"  - {item}")
    checks = index_payload.get("checks") or []
    if checks:
        print("- Checks:")
        for item in checks:
            name = item.get("name") if isinstance(item, dict) else None
            status = item.get("status") if isinstance(item, dict) else None
            path = item.get("path") if isinstance(item, dict) else None
            label = f"{name}: {status}" if name else str(item)
            if path:
                label += f" ({path})"
            print(f"  - {label}")

    events = _events.read_events(target, ticket, limit=args.events)
    if events:
        print("- Events:")
        for entry in events:
            line = f"{entry.get('ts')} [{entry.get('type')}]"
            status = entry.get("status")
            if status:
                line += f" {status}"
            details = entry.get("details")
            if isinstance(details, dict) and details.get("summary"):
                line += f" — {details.get('summary')}"
            print(f"  - {line}")
    test_events = _tests_log.read_log(target, ticket, limit=args.events)
    if test_events:
        print("- Tests log:")
        for entry in test_events:
            line = f"{entry.get('ts')} [{entry.get('status')}]"
            details = entry.get("details")
            if isinstance(details, dict) and details.get("summary"):
                line += f" — {details.get('summary')}"
            print(f"  - {line}")
    return 0


def _tests_log_command(args: argparse.Namespace) -> int:
    _, target = _require_workflow_root(Path(args.target).resolve())
    ticket, context = _require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    details: Dict[str, Any] = {}
    if args.summary:
        details["summary"] = args.summary
    if args.details:
        try:
            extra = json.loads(args.details)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid --details JSON: {exc}") from exc
        if isinstance(extra, dict):
            details.update(extra)
    from aidd_runtime.reports import tests_log as _tests_log

    _tests_log.append_log(
        target,
        ticket=ticket,
        slug_hint=context.slug_hint,
        status=args.status,
        details=details or None,
        source=args.source,
    )
    return 0

def _reviewer_tests_command(args: argparse.Namespace) -> None:
    _, target = _require_workflow_root(Path(args.target).resolve())

    ticket, context = _require_ticket(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )

    reviewer_cfg = _reviewer_gate_config(target)
    marker_template = str(
        reviewer_cfg.get("marker")
        or reviewer_cfg.get("tests_marker")
        or DEFAULT_REVIEWER_MARKER
    )
    marker_path = _reviewer_marker_path(target, marker_template, ticket, context.slug_hint)
    rel_marker = marker_path.relative_to(target).as_posix()

    if args.clear:
        if marker_path.exists():
            marker_path.unlink()
            print(f"[aidd] reviewer marker cleared ({rel_marker}).")
        else:
            print(f"[aidd] reviewer marker not found at {rel_marker}.")
        _maybe_sync_index(target, ticket, context.slug_hint, reason="reviewer-tests")
        return

    status = (args.status or "required").strip().lower()
    alias_map = {"skip": "skipped"}
    status = alias_map.get(status, status)

    def _extract_values(primary_key: str, legacy_key: str, fallback: Sequence[str]) -> list[str]:
        raw = reviewer_cfg.get(primary_key)
        if raw is None:
            raw = reviewer_cfg.get(legacy_key)
        if raw is None:
            source = fallback
        elif isinstance(raw, list):
            source = raw
        else:
            source = [raw]
        values = [str(value).strip().lower() for value in source if str(value).strip()]
        return values or list(fallback)

    required_values = _extract_values("required_values", "requiredValues", DEFAULT_REVIEWER_REQUIRED)
    optional_values = _extract_values("optional_values", "optionalValues", DEFAULT_REVIEWER_OPTIONAL)
    allowed_values = {*required_values, *optional_values}
    if status not in allowed_values:
        choices = ", ".join(sorted(allowed_values))
        raise ValueError(f"status must be one of: {choices}")

    field_name = str(
        reviewer_cfg.get("tests_field")
        or reviewer_cfg.get("field")
        or DEFAULT_REVIEWER_FIELD
    )

    requested_by = args.requested_by or os.getenv("GIT_AUTHOR_NAME") or os.getenv("USER") or ""
    record: dict = {}
    if marker_path.exists():
        try:
            record = json.loads(marker_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            record = {}

    record.update(
        {
            "ticket": ticket,
            "slug": context.slug_hint or ticket,
            field_name: status,
            "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
    )
    if requested_by:
        record["requested_by"] = requested_by
    if args.note:
        record["note"] = args.note
    elif "note" in record and not record["note"]:
        record.pop("note", None)

    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    state_label = "required" if status in required_values else status
    print(f"[aidd] reviewer marker updated ({rel_marker} → {state_label}).")
    if status in required_values:
        print("[aidd] format-and-test will trigger test tasks after the next write/edit.")
    _maybe_sync_index(target, ticket, context.slug_hint, reason="reviewer-tests")


def _review_report_command(args: argparse.Namespace) -> int:
    _, target = _require_workflow_root(Path(args.target).resolve())

    context = _resolve_feature_context(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    ticket = (context.resolved_ticket or "").strip()
    slug_hint = (context.slug_hint or ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active_ticket via /idea-new.")

    branch = args.branch or _detect_branch(target)

    def _fmt(text: str) -> str:
        return (
            text.replace("{ticket}", ticket)
            .replace("{slug}", slug_hint or ticket)
            .replace("{branch}", branch or "")
        )

    report_template = args.report or _review_report_template(target)
    report_text = _fmt(report_template)
    report_path = _resolve_path_for_target(Path(report_text), target)

    if args.findings and args.findings_file:
        raise ValueError("use --findings or --findings-file (not both)")

    input_payload = None
    if args.findings_file:
        try:
            input_payload = json.loads(Path(args.findings_file).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in --findings-file: {exc}") from exc
    elif args.findings:
        try:
            input_payload = json.loads(args.findings)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON for --findings: {exc}") from exc
    elif not args.status and not args.summary:
        raise ValueError("provide --findings or --findings-file, or update --status/--summary")

    def _extract_findings(raw: object) -> List[Dict]:
        if raw is None:
            return []
        if isinstance(raw, dict) and "findings" in raw:
            raw = raw.get("findings")
        if isinstance(raw, dict) and raw.get("cols") and raw.get("rows"):
            raw = _inflate_columnar(raw)
        if isinstance(raw, dict):
            if any(key in raw for key in ("title", "severity", "details", "recommendation", "scope", "id")):
                raw = [raw]
            else:
                return []
        if isinstance(raw, list):
            return [entry for entry in raw if isinstance(entry, dict)]
        return []

    existing_payload: Dict[str, Any] = {}
    existing_findings: List[Dict] = []
    if report_path.exists():
        try:
            existing_payload = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_payload = {}
    if isinstance(existing_payload, dict):
        existing_findings = _extract_findings(existing_payload.get("findings"))

    def _normalize_signature_text(value: object) -> str:
        return " ".join(str(value or "").strip().split()).lower()

    def _extract_title(entry: Dict, fallback: Optional[Dict[str, Any]] = None) -> str:
        title = entry.get("title") or entry.get("summary")
        if not title and fallback:
            title = fallback.get("title")
        return str(title or "").strip() or "issue"

    def _extract_scope(entry: Dict, fallback: Optional[Dict[str, Any]] = None) -> str:
        scope = entry.get("scope")
        if not scope and fallback:
            scope = fallback.get("scope")
        return str(scope or "").strip()

    def _finding_signature(entry: Dict, fallback: Optional[Dict[str, Any]] = None) -> str:
        raw_title = entry.get("title") or entry.get("summary")
        if not raw_title and fallback:
            raw_title = fallback.get("title") or fallback.get("summary")
        if not raw_title:
            return ""
        title = _normalize_signature_text(raw_title)
        raw_scope = entry.get("scope")
        if not raw_scope and fallback:
            raw_scope = fallback.get("scope")
        scope = _normalize_signature_text(raw_scope)
        return f"{scope}::{title}"

    def _stable_review_id(scope: str, title: str) -> str:
        return _stable_task_id("review", scope, title)

    def _normalize_finding(
        entry: Dict,
        *,
        existing: Dict[str, Any],
        now: str,
        fallback_id: str | None = None,
    ) -> Dict:
        severity = str(entry.get("severity") or existing.get("severity") or "info").strip().lower() or "info"
        scope = _extract_scope(entry, existing)
        title = _extract_title(entry, existing)
        details = str(entry.get("details") or existing.get("details") or "").strip()
        recommendation = str(entry.get("recommendation") or entry.get("action") or existing.get("recommendation") or "").strip()
        blocking_value = entry.get("blocking")
        if blocking_value is None:
            blocking_value = existing.get("blocking")
        if blocking_value is None:
            blocking_value = severity in {"blocker", "critical"}
        raw_id = str(entry.get("id") or "").strip()
        if not raw_id:
            raw_id = fallback_id or _stable_review_id(scope, title)
        merged = dict(existing)
        merged.update(entry)
        merged.update(
            {
                "id": raw_id,
                "severity": severity,
                "scope": scope,
                "title": title,
                "details": details,
                "recommendation": recommendation,
                "blocking": bool(blocking_value),
            }
        )
        first_seen = (
            existing.get("first_seen_at")
            or existing.get("created_at")
            or existing.get("generated_at")
        )
        merged["first_seen_at"] = first_seen or now
        merged["last_seen_at"] = now
        return merged

    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    existing_by_id: Dict[str, Dict] = {}
    existing_by_sig: Dict[str, Dict] = {}
    sig_collisions: set[str] = set()
    normalized_existing: List[Dict] = []
    for entry in existing_findings:
        signature = _finding_signature(entry, entry)
        normalized = _normalize_finding(
            entry,
            existing=entry,
            now=entry.get("last_seen_at") or now,
            fallback_id=_stable_review_id(
                _extract_scope(entry, entry),
                _extract_title(entry, entry),
            ),
        )
        entry_id = str(normalized.get("id") or "").strip()
        if entry_id:
            existing_by_id[entry_id] = normalized
        if signature:
            if signature in existing_by_sig:
                sig_collisions.add(signature)
            else:
                existing_by_sig[signature] = normalized
        normalized_existing.append(normalized)

    new_findings = _extract_findings(input_payload)
    new_by_id: Dict[str, Dict] = {}
    for entry in new_findings:
        entry_id = str(entry.get("id") or "").strip()
        signature = ""
        matched_existing: Dict[str, Any] = {}
        if not entry_id:
            signature = _finding_signature(entry)
            if signature and signature in existing_by_sig and signature not in sig_collisions:
                matched_existing = existing_by_sig[signature]
                entry_id = str(matched_existing.get("id") or "").strip()
        fallback_id = None
        if not entry_id:
            scope = _extract_scope(entry)
            title = _extract_title(entry)
            fallback_id = _stable_review_id(scope, title)
        candidate = _normalize_finding(
            entry,
            existing=matched_existing or existing_by_id.get(entry_id, {}),
            now=now,
            fallback_id=fallback_id,
        )
        entry_id = str(candidate.get("id") or "").strip()
        if entry_id:
            new_by_id[entry_id] = candidate

    merged_findings: List[Dict] = []
    replaced_ids: set[str] = set()
    for entry in normalized_existing:
        entry_id = str(entry.get("id") or "").strip()
        if entry_id and entry_id in new_by_id:
            merged_findings.append(new_by_id[entry_id])
            replaced_ids.add(entry_id)
        else:
            merged_findings.append(entry)
    for entry in new_by_id.values():
        entry_id = str(entry.get("id") or "").strip()
        if entry_id and entry_id in replaced_ids:
            continue
        merged_findings.append(entry)

    record: Dict[str, Any] = existing_payload if isinstance(existing_payload, dict) else {}
    record.update(
        {
            "ticket": ticket,
            "slug": slug_hint or ticket,
            "kind": "review",
            "stage": "review",
            "updated_at": now,
        }
    )
    if branch:
        record["branch"] = branch
    record.setdefault("generated_at", now)
    if args.status:
        record["status"] = str(args.status).strip().lower()
    if args.summary:
        record["summary"] = str(args.summary).strip()
    if merged_findings:
        record["findings"] = merged_findings
    elif "findings" in record:
        record["findings"] = record.get("findings") or []

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rel_report = _rel_path(report_path, target)
    print(f"[aidd] review report saved to {rel_report}.")
    _maybe_sync_index(target, ticket, slug_hint or None, reason="review-report")
    return 0


def _load_qa_tests_config(root: Path) -> tuple[list[list[str]], bool]:
    config_path = root / "config" / "gates.json"
    commands: list[list[str]] = []
    allow_skip = True
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return _default_qa_test_command(), allow_skip

    qa_cfg = data.get("qa") or {}
    tests_cfg = qa_cfg.get("tests") or {}
    allow_skip = bool(tests_cfg.get("allow_skip", True))
    raw_commands = tests_cfg.get("commands", _default_qa_test_command())
    if isinstance(raw_commands, str):
        raw_commands = [raw_commands]
    if isinstance(raw_commands, list):
        for entry in raw_commands:
            parts: list[str] = []
            if isinstance(entry, list):
                parts = [str(item) for item in entry if str(item)]
            elif isinstance(entry, str):
                try:
                    parts = [token for token in shlex.split(entry) if token]
                except ValueError:
                    continue
            if parts:
                commands.append(parts)

    if not commands:
        commands = _default_qa_test_command()
    return commands, allow_skip


def _run_qa_tests(
    target: Path,
    *,
    ticket: str,
    slug_hint: str | None,
    branch: str | None,
    report_path: Path,
    allow_missing: bool,
) -> tuple[list[dict], str]:
    commands, allow_skip_cfg = _load_qa_tests_config(target)
    allow_skip = allow_missing or allow_skip_cfg

    tests_executed: list[dict] = []
    if not commands:
        summary = "skipped"
        return tests_executed, summary

    logs_dir = report_path.parent
    base_name = report_path.stem
    summary = "not-run"

    for index, cmd in enumerate(commands, start=1):
        log_path = logs_dir / f"{base_name}-tests{'' if len(commands) == 1 else f'-{index}'}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        status = "fail"
        exit_code: Optional[int] = None
        output = ""
        try:
            proc = subprocess.run(
                cmd,
                cwd=target,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            output = proc.stdout or ""
            exit_code = proc.returncode
            status = "pass" if proc.returncode == 0 else "fail"
        except FileNotFoundError as exc:
            status = "fail"
            output = f"command not found: {cmd[0]} ({exc})"
        log_path.write_text(output, encoding="utf-8")

        tests_executed.append(
            {
                "command": " ".join(cmd),
                "status": status,
                "log": _rel_path(log_path, target),
                "exit_code": exit_code,
            }
        )

    if any(entry.get("status") == "fail" for entry in tests_executed):
        summary = "fail"
    else:
        summary = "pass" if tests_executed else "not-run"

    if summary in {"not-run", "skipped"} and allow_skip:
        summary = "skipped"

    return tests_executed, summary


def _qa_command(args: argparse.Namespace) -> int:
    _, target = _require_workflow_root(Path(args.target).resolve())

    context = _resolve_feature_context(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    ticket = (context.resolved_ticket or "").strip()
    slug_hint = (context.slug_hint or ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active_ticket via /idea-new.")

    branch = args.branch or _detect_branch(target)

    def _fmt(text: str) -> str:
        return (
            text.replace("{ticket}", ticket)
            .replace("{slug}", slug_hint or ticket)
            .replace("{branch}", branch or "")
        )

    report_template = args.report or "aidd/reports/qa/{ticket}.json"
    report_text = _fmt(report_template)
    report_path = _resolve_path_for_target(Path(report_text), target)

    allow_no_tests = bool(
        getattr(args, "allow_no_tests", False)
        or os.getenv("CLAUDE_QA_ALLOW_NO_TESTS", "").strip() == "1"
    )
    skip_tests = bool(getattr(args, "skip_tests", False) or os.getenv("CLAUDE_QA_SKIP_TESTS", "").strip() == "1")

    tests_executed: list[dict] = []
    tests_summary = "skipped" if skip_tests else "not-run"

    if not skip_tests:
        tests_executed, tests_summary = _run_qa_tests(
            target,
            ticket=ticket,
            slug_hint=slug_hint or None,
            branch=branch,
            report_path=report_path,
            allow_missing=allow_no_tests,
        )
        if tests_summary == "fail":
            print("[aidd] QA tests failed; see aidd/reports/qa/*-tests.log.")
        elif tests_summary == "skipped":
            print("[aidd] QA tests skipped (allow_no_tests enabled or no commands configured).")
        else:
            print("[aidd] QA tests completed.")

    qa_args = ["--target", str(target)]
    if args.gate:
        qa_args.append("--gate")
    if args.dry_run:
        qa_args.append("--dry-run")
    if args.emit_json:
        qa_args.append("--emit-json")
    if args.format:
        qa_args.extend(["--format", args.format])
    if args.block_on:
        qa_args.extend(["--block-on", args.block_on])
    if args.warn_on:
        qa_args.extend(["--warn-on", args.warn_on])
    if args.scope:
        for scope in args.scope:
            qa_args.extend(["--scope", scope])
    if args.emit_patch:
        qa_args.append("--emit-patch")
    if args.pack_only:
        qa_args.append("--pack-only")

    qa_args.extend(["--ticket", ticket])
    if slug_hint and slug_hint != ticket:
        qa_args.extend(["--slug-hint", slug_hint])
    if branch:
        qa_args.extend(["--branch", branch])
    if report_path:
        qa_args.extend(["--report", str(report_path)])

    _, allow_skip_cfg = _load_qa_tests_config(target)
    allow_no_tests_env = allow_no_tests or allow_skip_cfg

    old_env = {
        "QA_TESTS_SUMMARY": os.environ.get("QA_TESTS_SUMMARY"),
        "QA_TESTS_EXECUTED": os.environ.get("QA_TESTS_EXECUTED"),
        "QA_ALLOW_NO_TESTS": os.environ.get("QA_ALLOW_NO_TESTS"),
    }
    os.environ["QA_TESTS_SUMMARY"] = tests_summary
    os.environ["QA_TESTS_EXECUTED"] = json.dumps(tests_executed, ensure_ascii=False)
    os.environ["QA_ALLOW_NO_TESTS"] = "1" if allow_no_tests_env else "0"
    try:
        exit_code = _qa_agent.main(qa_args)
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    if tests_summary == "fail":
        exit_code = max(exit_code, 1)
    elif tests_summary in {"not-run", "skipped"} and not allow_no_tests_env:
        exit_code = max(exit_code, 1)

    try:
        from aidd_runtime.reports import events as _events
        payload = None
        report_for_event: Path | None = None
        if report_path.exists():
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            report_for_event = report_path
        else:
            from aidd_runtime.reports.loader import load_report_for_path

            payload, source, report_paths = load_report_for_path(report_path, prefer_pack=True)
            report_for_event = report_paths.pack_path if source == "pack" else report_paths.json_path

        if payload and report_for_event:
            _events.append_event(
                target,
                ticket=ticket,
                slug_hint=slug_hint or None,
                event_type="qa",
                status=str(payload.get("status") or ""),
                details={"summary": payload.get("summary")},
                report_path=Path(_rel_path(report_for_event, target)),
                source="aidd qa",
            )
    except Exception:
        pass

    if not args.dry_run:
        _maybe_sync_index(target, ticket, slug_hint or None, reason="qa")
    return exit_code


def _progress_command(args: argparse.Namespace) -> int:
    _, target = _require_workflow_root(Path(args.target).resolve())

    context = _resolve_feature_context(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    ticket = context.resolved_ticket
    branch = args.branch or _detect_branch(target)
    config = _progress.ProgressConfig.load(target)
    result = _progress.check_progress(
        root=target,
        ticket=ticket,
        slug_hint=context.slug_hint,
        source=args.source,
        branch=branch,
        config=config,
    )

    try:
        from aidd_runtime.reports import events as _events

        _events.append_event(
            target,
            ticket=ticket or "",
            slug_hint=context.slug_hint,
            event_type="progress",
            status=result.status,
            details={
                "source": args.source,
                "message": result.message,
                "code_files": len(result.code_files),
                "new_items": len(result.new_items),
            },
            source="aidd progress",
        )
    except Exception:
        pass
    try:
        if result.status == "ok":
            _maybe_write_test_checkpoint(target, ticket, context.slug_hint, args.source)
    except Exception:
        pass
    _maybe_sync_index(target, ticket, context.slug_hint, reason="progress")

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return result.exit_code()

    def _print_items(items: Sequence[str], prefix: str = "  - ", limit: int = 5) -> None:
        for index, item in enumerate(items):
            if index == limit:
                remaining = len(items) - limit
                print(f"{prefix}… (+{remaining})")
                break
            print(f"{prefix}{item}")

    if result.status.startswith("error:"):
        print(result.message or "BLOCK: проверка прогресса не пройдена.")
        if args.verbose and result.code_files:
            print("Изменённые файлы:")
            _print_items(result.code_files)
        return result.exit_code()

    if result.status.startswith("skip:"):
        print(result.message or "Прогресс-чек пропущен.")
        if args.verbose and result.code_files:
            print("Изменённые файлы:")
            _print_items(result.code_files)
        return 0

    label = _format_ticket_label(context)
    print(f"✅ Прогресс tasklist для `{label}` подтверждён.")
    if result.new_items:
        print("Новые чекбоксы:")
        _print_items(result.new_items)
    if args.verbose and result.code_files:
        print("Затронутые файлы:")
        _print_items(result.code_files)
    return 0

def _resolve_claude_dir(target: Path) -> Path:
    candidate = target / ".claude"
    if candidate.exists():
        return candidate
    if target.name == DEFAULT_PROJECT_SUBDIR:
        return target.parent / ".claude"
    return candidate

def _read_template_version(target: Path) -> str | None:
    version_file = _resolve_claude_dir(target) / ".template_version"
    if not version_file.exists():
        return None
    return version_file.read_text(encoding="utf-8").strip() or None


def _write_template_version(target: Path) -> None:
    version_file = _resolve_claude_dir(target) / ".template_version"
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(f"{VERSION}\n", encoding="utf-8")


def _resolve_feature_context(
    target: Path,
    *,
    ticket: Optional[str] = None,
    slug_hint: Optional[str] = None,
) -> FeatureIdentifiers:
    return resolve_identifiers(target, ticket=ticket, slug_hint=slug_hint)


def _require_ticket(
    target: Path,
    *,
    ticket: Optional[str] = None,
    slug_hint: Optional[str] = None,
) -> tuple[str, FeatureIdentifiers]:
    context = _resolve_feature_context(target, ticket=ticket, slug_hint=slug_hint)
    resolved = (context.resolved_ticket or "").strip()
    if not resolved:
        raise ValueError(
            "feature ticket is required; pass --ticket or set docs/.active_ticket via /idea-new."
        )
    return resolved, context


def _auto_index_enabled() -> bool:
    raw = os.getenv("AIDD_INDEX_AUTO", "").strip().lower()
    if not raw:
        return True
    return raw not in {"0", "false", "no", "off"}


def _maybe_sync_index(
    target: Path,
    ticket: Optional[str],
    slug_hint: Optional[str],
    *,
    reason: str = "",
    announce: bool = False,
) -> None:
    if not _auto_index_enabled():
        return
    if not ticket:
        return
    ticket = str(ticket).strip()
    if not ticket:
        return
    slug = (slug_hint or ticket).strip() or ticket
    try:
        from aidd_runtime.tools import index_sync as _index_sync

        index_path = _index_sync.write_index(target, ticket, slug)
        if announce:
            rel = _rel_path(index_path, target)
            print(f"[index] index saved to {rel}.")
    except Exception as exc:
        label = f" ({reason})" if reason else ""
        print(f"[index] warning{label}: failed to update index ({exc}).", file=sys.stderr)


def _format_ticket_label(context: FeatureIdentifiers, fallback: str = "активной фичи") -> str:
    ticket = (context.resolved_ticket or "").strip() or fallback
    if context.slug_hint and context.slug_hint.strip() and context.slug_hint.strip() != ticket:
        return f"{ticket} (slug hint: {context.slug_hint.strip()})"
    return ticket


def _settings_path(target: Path) -> Path:
    return _resolve_claude_dir(target) / "settings.json"


def _load_settings_json(target: Path) -> dict:
    settings_file = _settings_path(target)
    if not settings_file.exists():
        return {}
    try:
        return json.loads(settings_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"cannot parse {settings_file}: {exc}") from exc


def _load_tests_settings(target: Path) -> dict:
    settings = _load_settings_json(target)
    automation = settings.get("automation") or {}
    tests_cfg = automation.get("tests")
    return tests_cfg if isinstance(tests_cfg, dict) else {}


def _normalize_checkpoint_triggers(value: object) -> list[str]:
    if value is None:
        return ["progress"]
    if isinstance(value, (list, tuple)):
        items = [str(item).strip().lower() for item in value if str(item).strip()]
    else:
        items = [item.strip().lower() for item in str(value).replace(",", " ").split() if item.strip()]
    return items or ["progress"]


def _maybe_write_test_checkpoint(
    target: Path,
    ticket: Optional[str],
    slug_hint: Optional[str],
    source: str,
) -> None:
    if not ticket:
        return
    tests_cfg = _load_tests_settings(target)
    cadence = str(tests_cfg.get("cadence") or "on_stop").strip().lower()
    if cadence != "checkpoint":
        return
    triggers = _normalize_checkpoint_triggers(
        tests_cfg.get("checkpointTrigger") or tests_cfg.get("checkpoint_trigger")
    )
    if "progress" not in triggers:
        return
    checkpoint_path = target / ".cache" / "test-checkpoint.json"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ticket": ticket,
        "slug_hint": slug_hint or ticket,
        "trigger": "progress",
        "source": source,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    checkpoint_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _reviewer_gate_config(target: Path) -> dict:
    tests_cfg = _load_tests_settings(target)
    reviewer_cfg = tests_cfg.get("reviewerGate") if isinstance(tests_cfg, dict) else None
    return reviewer_cfg if isinstance(reviewer_cfg, dict) else {}


def _reviewer_marker_path(target: Path, template: str, ticket: str, slug_hint: Optional[str]) -> Path:
    rel_text = template.replace("{ticket}", ticket)
    if "{slug}" in template:
        rel_text = rel_text.replace("{slug}", slug_hint or ticket)
    marker_path = _resolve_path_for_target(Path(rel_text), target)
    target_root = target.resolve()
    if not _is_relative_to(marker_path, target_root):
        raise ValueError(
            f"reviewer marker path {marker_path} escapes project root {target_root}"
        )
    return marker_path


def _load_gates_config(target: Path) -> dict:
    config_path = target / "config" / "gates.json"
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _review_report_template(target: Path) -> str:
    config = _load_gates_config(target)
    reviewer_cfg = config.get("reviewer") if isinstance(config, dict) else None
    if not isinstance(reviewer_cfg, dict):
        reviewer_cfg = {}
    return str(
        reviewer_cfg.get("marker")
        or reviewer_cfg.get("tests_marker")
        or DEFAULT_REVIEW_REPORT
    )


def _detect_branch(target: Path) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=target,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return None
    if proc.returncode != 0:
        return None
    branch = proc.stdout.strip()
    if not branch or branch.upper() == "HEAD":
        return None
    return branch


_TASK_ID_RE = re.compile(r"\bid:\s*([A-Za-z0-9_.:-]+)")
_TASK_ID_SIGNATURE_RE = re.compile(r"(,?\s*id:\s*[A-Za-z0-9_.:-]+)")


def _stable_task_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha1()
    digest.update(prefix.encode("utf-8"))
    for part in parts:
        normalized = " ".join(str(part or "").strip().split())
        digest.update(b"|")
        digest.update(normalized.encode("utf-8"))
    return digest.hexdigest()[:12]


def _task_id_from_line(line: str) -> str | None:
    match = _TASK_ID_RE.search(line)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _task_signature(line: str) -> str:
    normalized = " ".join(line.strip().split())
    normalized = _TASK_ID_SIGNATURE_RE.sub("", normalized)
    normalized = normalized.replace(" ,", ",")
    lowered = normalized.lower()
    source_idx = lowered.rfind(" (source:")
    if source_idx != -1:
        head = normalized[:source_idx]
        tail = normalized[source_idx:]
        if " — " in head:
            head = head.split(" — ", 1)[0]
        normalized = head + tail
    return " ".join(normalized.strip().split())


def _format_task_suffix(report_label: str, task_id: str | None = None) -> str:
    parts = [f"source: {report_label}"]
    if task_id:
        parts.append(f"id: {task_id}")
    return f" ({', '.join(parts)})"


_HANDOFF_SECTION_HINTS: Dict[str, Tuple[str, ...]] = {
    "qa": (
        "## aidd:handoff_inbox",
        "## 3. qa / проверки",
        "## qa",
        "## 3. qa",
        "## 3. qa / проверки",
    ),
    "review": (
        "## aidd:handoff_inbox",
        "## 2. реализация",
        "## реализация",
        "## implementation",
        "## 2. implementation",
    ),
    "research": (
        "## aidd:handoff_inbox",
        "## 1. аналитика и дизайн",
        "## аналитика",
        "## research",
        "## 7. примечания",
    ),
}


def _resolve_path_for_target(path: Path, target: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    parts = path.parts
    if parts and parts[0] == ".":
        path = Path(*parts[1:])
        parts = path.parts
    if parts and parts[0] == DEFAULT_PROJECT_SUBDIR and target.name == DEFAULT_PROJECT_SUBDIR:
        path = Path(*parts[1:])
    return (target / path).resolve()


def _rel_path(path: Path, root: Path) -> str:
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
    if root.name == DEFAULT_PROJECT_SUBDIR:
        return f"{DEFAULT_PROJECT_SUBDIR}/{rel}"
    return rel


def _load_json_file(path: Path) -> Dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to parse {path}: {exc}") from exc


def _derive_tasks_from_findings(prefix: str, payload: Dict, report_label: str) -> List[str]:
    raw_findings = payload.get("findings") or []
    findings = _inflate_columnar(raw_findings) if isinstance(raw_findings, dict) else raw_findings
    tasks: List[str] = []
    prefix_key = prefix.lower().replace(" ", "-")
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        severity = str(finding.get("severity") or "").strip().lower() or "info"
        scope = str(finding.get("scope") or "").strip()
        title = str(finding.get("title") or "").strip() or "issue"
        details = str(finding.get("recommendation") or finding.get("details") or "").strip()
        raw_id = str(finding.get("id") or "").strip()
        if not raw_id:
            raw_id = _stable_task_id(prefix_key, scope, title)
        task_id = f"{prefix_key}:{raw_id}"
        scope_label = f" ({scope})" if scope else ""
        details_part = f" — {details}" if details else ""
        suffix = _format_task_suffix(report_label, task_id)
        tasks.append(f"- [ ] {prefix} [{severity}] {title}{scope_label}{details_part}{suffix}")
    return tasks


def _derive_tasks_from_tests(payload: Dict, report_label: str) -> List[str]:
    tasks: List[str] = []
    summary = str(payload.get("tests_summary") or "").strip().lower() or "not-run"
    raw_executed = payload.get("tests_executed") or []
    executed = _inflate_columnar(raw_executed) if isinstance(raw_executed, dict) else raw_executed
    if summary in {"skipped", "not-run"}:
        task_id = f"qa-tests:{_stable_task_id('qa-tests', summary)}"
        suffix = _format_task_suffix(report_label, task_id)
        tasks.append(f"- [ ] QA tests: запустить автотесты и приложить лог{suffix}")
    for entry in executed:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "").strip().lower()
        if status == "pass":
            continue
        command = str(entry.get("command") or "").strip() or "tests"
        log = str(entry.get("log") or entry.get("log_path") or "").strip()
        details = f" (лог: {log})" if log else ""
        status_label = status or "unknown"
        task_id = f"qa-tests:{_stable_task_id('qa-tests', status_label, command, log)}"
        suffix = _format_task_suffix(report_label, task_id)
        tasks.append(f"- [ ] QA tests: {status_label} → повторить `{command}`{details}{suffix}")
    if summary == "fail" and not any(str(entry.get("status") or "").strip().lower() == "fail" for entry in executed):
        task_id = f"qa-tests:{_stable_task_id('qa-tests', 'fail', 'summary')}"
        suffix = _format_task_suffix(report_label, task_id)
        tasks.append(f"- [ ] QA tests: исправить упавшие тесты{suffix}")
    return tasks


def _inflate_columnar(section: object) -> List[Dict]:
    if not isinstance(section, dict):
        return list(section) if isinstance(section, list) else []
    cols = section.get("cols")
    rows = section.get("rows")
    if not isinstance(cols, list) or not isinstance(rows, list):
        return []
    inflated: List[Dict] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        inflated.append({str(col): row[idx] if idx < len(row) else None for idx, col in enumerate(cols)})
    return inflated


def _derive_tasks_from_research_context(payload: Dict, report_label: str, *, reuse_limit: int = 5) -> List[str]:
    tasks: List[str] = []
    profile = payload.get("profile") or {}
    recommendations = profile.get("recommendations") or []
    for rec in recommendations:
        rec_text = str(rec).strip()
        if not rec_text:
            continue
        task_id = f"research:{_stable_task_id('research', rec_text)}"
        suffix = _format_task_suffix(report_label, task_id)
        tasks.append(f"- [ ] Research: {rec_text}{suffix}")

    manual_notes = payload.get("manual_notes") or []
    for note in manual_notes:
        note_text = str(note).strip()
        if not note_text:
            continue
        task_id = f"research:{_stable_task_id('research', 'note', note_text)}"
        suffix = _format_task_suffix(report_label, task_id)
        tasks.append(f"- [ ] Research note: {note_text}{suffix}")

    raw_reuse = payload.get("reuse_candidates") or []
    reuse_candidates = _inflate_columnar(raw_reuse) if isinstance(raw_reuse, dict) else raw_reuse
    for candidate in reuse_candidates[:reuse_limit]:
        if not isinstance(candidate, dict):
            continue
        path = str(candidate.get("path") or "").strip()
        if not path:
            continue
        score = candidate.get("score")
        has_tests = candidate.get("has_tests")
        extra_parts = []
        if score is not None:
            extra_parts.append(f"score={score}")
        if has_tests:
            extra_parts.append("tests")
        suffix = f" ({', '.join(extra_parts)})" if extra_parts else ""
        task_id = f"research:{_stable_task_id('research', 'reuse', path, score, has_tests)}"
        task_suffix = _format_task_suffix(report_label, task_id)
        tasks.append(f"- [ ] Reuse candidate: {path}{suffix}{task_suffix}")
    return tasks


def _derive_handoff_placeholder(source: str, ticket: str, report_label: str) -> List[str]:
    source_key = source.strip().lower()
    if source_key == "qa":
        task_id = f"qa:report-{_stable_task_id('qa-report', ticket)}"
        suffix = _format_task_suffix(report_label, task_id)
        return [f"- [ ] QA report: подтвердить отсутствие блокеров{suffix}"]
    if source_key == "review":
        task_id = f"review:report-{_stable_task_id('review-report', ticket)}"
        suffix = _format_task_suffix(report_label, task_id)
        return [f"- [ ] Review report: подтвердить отсутствие замечаний{suffix}"]
    return []


def _dedupe_tasks(tasks: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    deduped: List[str] = []
    for task in tasks:
        normalized = " ".join(task.strip().split())
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(task.strip())
    return deduped


def _merge_handoff_tasks(existing: Sequence[str], new_tasks: Sequence[str], *, append: bool) -> List[str]:
    if not append:
        return _dedupe_tasks(new_tasks)
    existing_lines = list(existing)
    new_by_id: Dict[str, str] = {}
    new_by_sig: Dict[str, str] = {}
    sig_collisions: set[str] = set()
    for line in new_tasks:
        task_id = _task_id_from_line(line)
        if task_id:
            new_by_id[task_id] = line
        signature = _task_signature(line)
        if signature:
            if signature in new_by_sig:
                sig_collisions.add(signature)
            else:
                new_by_sig[signature] = line
    merged: List[str] = []
    replaced_ids: set[str] = set()
    replaced_sigs: set[str] = set()
    for line in existing_lines:
        task_id = _task_id_from_line(line)
        if task_id and task_id in new_by_id:
            merged.append(new_by_id[task_id])
            replaced_ids.add(task_id)
            continue
        signature = _task_signature(line)
        if signature and signature in new_by_sig and signature not in sig_collisions:
            merged.append(new_by_sig[signature])
            replaced_sigs.add(signature)
            continue
        merged.append(line)
    for line in new_tasks:
        task_id = _task_id_from_line(line)
        if task_id and task_id in replaced_ids:
            continue
        signature = _task_signature(line)
        if signature and signature in replaced_sigs:
            continue
        merged.append(line)
    return _dedupe_tasks(merged)


def _extract_handoff_block(lines: List[str], source: str) -> tuple[int, int, List[str]]:
    start = -1
    end = -1
    marker = f"handoff:{source}"
    for idx, line in enumerate(lines):
        lowered = line.lower()
        if marker in lowered and "start" in lowered:
            start = idx
            break
    if start != -1:
        for idx in range(start + 1, len(lines)):
            lowered = lines[idx].lower()
            if marker in lowered and "end" in lowered:
                end = idx
                break
    if start != -1 and end == -1:
        end = start
    existing: List[str] = []
    if start != -1 and end != -1:
        existing = [
            line
            for line in lines[start + 1 : end]
            if line.strip().startswith("- [ ]")
        ]
    return start, end, existing


def _find_section(lines: List[str], candidates: Sequence[str]) -> tuple[int, Optional[str]]:
    if not candidates:
        return len(lines), None
    lowered_candidates = [candidate.strip().lower() for candidate in candidates if candidate.strip()]
    heading_idx = None
    heading_label = None
    for idx, line in enumerate(lines):
        stripped = line.strip().lower()
        if stripped.startswith("##"):
            for candidate in lowered_candidates:
                if stripped.startswith(candidate):
                    heading_idx = idx
                    heading_label = lines[idx].strip()
                    break
        if heading_idx is not None:
            break
    if heading_idx is None:
        return len(lines), None
    insert_idx = len(lines)
    for idx in range(heading_idx + 1, len(lines)):
        stripped = lines[idx].strip()
        if stripped.startswith("##"):
            insert_idx = idx
            break
    return insert_idx, heading_label


def _apply_handoff_tasks(
    text: str,
    *,
    source: str,
    report_label: str,
    tasks: Sequence[str],
    append: bool,
    section_candidates: Sequence[str],
) -> tuple[str, Optional[str], bool]:
    if not tasks:
        return text, None, False
    lines = text.splitlines()
    start, end, existing = _extract_handoff_block(lines, source)
    combined = _merge_handoff_tasks(existing, tasks, append=append)
    if not combined:
        return text, None, False

    if start != -1 and end != -1:
        del lines[start : end + 1]

    block_lines = [f"<!-- handoff:{source} start (source: {report_label}) -->"]
    block_lines.extend(combined)
    block_lines.append(f"<!-- handoff:{source} end -->")

    insert_idx, heading_label = _find_section(lines, section_candidates)
    prepend_blank = insert_idx > 0 and lines[insert_idx - 1].strip()
    if prepend_blank:
        block_lines.insert(0, "")
    append_blank = insert_idx < len(lines) and lines[insert_idx : insert_idx + 1] and lines[insert_idx].strip()
    if append_blank:
        block_lines.append("")
    new_lines = lines[:insert_idx] + block_lines + lines[insert_idx:]
    new_text = "\n".join(new_lines)
    if not new_text.endswith("\n"):
        new_text += "\n"
    changed = new_text != text
    return new_text, heading_label, changed


def _tasks_derive_command(args: argparse.Namespace) -> int:
    _, target = _require_workflow_root(Path(args.target).resolve())

    context = _resolve_feature_context(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    ticket = (context.resolved_ticket or "").strip()
    slug_hint = (context.slug_hint or ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active_ticket via /idea-new.")

    source = (args.source or "").strip().lower()
    default_report = {
        "qa": "aidd/reports/qa/{ticket}.json",
        "research": "aidd/reports/research/{ticket}-context.json",
    }.get(source)
    if source == "review":
        default_report = _review_report_template(target)
    report_template = args.report or default_report
    if not report_template:
        raise ValueError("unsupported source; expected qa|research|review")

    def _fmt(text: str) -> str:
        return (
            text.replace("{ticket}", ticket)
            .replace("{slug}", slug_hint or ticket)
        )

    report_path = _resolve_path_for_target(Path(_fmt(report_template)), target)

    def _env_truthy(value: str | None) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "y"}

    prefer_pack = bool(getattr(args, "prefer_pack", False) or _env_truthy(os.getenv("AIDD_PACK_FIRST")))

    def _load_with_pack(path: Path, *, prefer_pack_first: bool) -> tuple[Dict, str]:
        from aidd_runtime.reports.loader import load_report_for_path

        payload, source_kind, report_paths = load_report_for_path(path, prefer_pack=prefer_pack_first)
        label_path = report_paths.pack_path if source_kind == "pack" else report_paths.json_path
        return payload, _rel_path(label_path, target)

    is_pack_path = report_path.name.endswith(".pack.yaml") or report_path.name.endswith(".pack.toon")
    if source == "research" and (prefer_pack or is_pack_path or not report_path.exists()):
        payload, report_label = _load_with_pack(report_path, prefer_pack_first=True)
    elif source == "qa" and (is_pack_path or not report_path.exists()):
        payload, report_label = _load_with_pack(report_path, prefer_pack_first=True)
    else:
        report_label = _rel_path(report_path, target)
        if not report_path.exists():
            raise FileNotFoundError(f"{source} report not found at {report_label}")
        payload = _load_json_file(report_path)
    if source == "qa":
        derived_tasks = _derive_tasks_from_findings("QA", payload, report_label)
        derived_tasks.extend(_derive_tasks_from_tests(payload, report_label))
    elif source == "review":
        derived_tasks = _derive_tasks_from_findings("Review", payload, report_label)
    elif source == "research":
        derived_tasks = _derive_tasks_from_research_context(payload, report_label)
    else:
        derived_tasks = []

    derived_tasks = _dedupe_tasks(derived_tasks)
    if not derived_tasks:
        derived_tasks = _dedupe_tasks(_derive_handoff_placeholder(source, ticket, report_label))
    if not derived_tasks:
        print(f"[aidd] no tasks found in {source} report ({report_label}).")
        return 0

    tasklist_rel = Path("docs") / "tasklist" / f"{ticket}.md"
    tasklist_path = target / tasklist_rel
    if not tasklist_path.exists():
        raise FileNotFoundError(
            f"tasklist not found at {tasklist_rel}; create it via /tasks-new {ticket}."
        )
    tasklist_text = tasklist_path.read_text(encoding="utf-8")

    updated_text, heading_label, changed = _apply_handoff_tasks(
        tasklist_text,
        source=source,
        report_label=report_label,
        tasks=derived_tasks,
        append=bool(args.append),
        section_candidates=_HANDOFF_SECTION_HINTS.get(source, ()),
    )

    section_display = heading_label or "end of file"
    if args.dry_run:
        print(
            f"[aidd] (dry-run) {len(derived_tasks)} task(s) "
            f"from {source} → {tasklist_rel} (section: {section_display})"
        )
        for task in derived_tasks:
            print(f"  {task}")
        return 0

    if not changed:
        print(f"[aidd] tasklist already up to date for {source} report ({report_label}).")
        return 0

    tasklist_path.write_text(updated_text, encoding="utf-8")
    print(
        f"[aidd] added {len(derived_tasks)} task(s) "
        f"from {source} report ({report_label}) to {tasklist_rel} "
        f"(section: {section_display}; mode={'append' if args.append else 'replace'})."
    )
    _maybe_sync_index(target, ticket, slug_hint or None, reason="tasks-derive")
    return 0


def _ensure_research_doc(
    target: Path,
    ticket: str,
    slug_hint: Optional[str],
    *,
    template_overrides: Optional[Dict[str, str]] = None,
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


def _is_relative_to(path: Path, ancestor: Path) -> bool:
    try:
        path.relative_to(ancestor)
        return True
    except ValueError:
        return False

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aidd-runtime",
        description="Bootstrap and manage the Claude Code workflow.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init", help="Generate workflow scaffolding in the target directory."
    )
    init_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root for the workflow (default: current; workflow always lives in ./aidd).",
    )
    init_parser.add_argument(
        "--commit-mode",
        choices=("ticket-prefix", "conventional", "mixed"),
        default="ticket-prefix",
        help="Commit message policy enforced in config/conventions.json.",
    )
    init_parser.add_argument(
        "--enable-ci",
        action="store_true",
        help="Add GitHub Actions workflow (manual trigger).",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files.",
    )
    init_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without modifying files.",
    )
    init_parser.set_defaults(func=_init_command)

    smoke_parser = subparsers.add_parser(
        "smoke", help="Run the bundled smoke test to validate the workflow bootstrap."
    )
    smoke_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Emit verbose logs when running the smoke scenario.",
    )
    smoke_parser.set_defaults(func=_smoke_command)

    set_active_feature_parser = subparsers.add_parser(
        "set-active-feature",
        help="Persist the active feature ticket and refresh Researcher targets.",
    )
    set_active_feature_parser.add_argument("ticket", help="Feature ticket identifier to persist.")
    set_active_feature_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    set_active_feature_parser.add_argument(
        "--paths",
        help="Optional colon-separated list of extra paths for Researcher scope.",
    )
    set_active_feature_parser.add_argument(
        "--keywords",
        help="Optional comma-separated keywords to seed Researcher search.",
    )
    set_active_feature_parser.add_argument(
        "--config",
        help="Path to conventions JSON with researcher section (defaults to config/conventions.json).",
    )
    set_active_feature_parser.add_argument(
        "--slug-note",
        dest="slug_note",
        help="Optional slug hint to persist alongside the ticket.",
    )
    set_active_feature_parser.add_argument(
        "--skip-prd-scaffold",
        action="store_true",
        help="Skip automatic docs/prd/<ticket>.prd.md scaffold creation.",
    )
    set_active_feature_parser.set_defaults(func=_set_active_feature_command)

    identifiers_parser = subparsers.add_parser(
        "identifiers",
        help="Resolve active feature identifiers (ticket and slug hint).",
    )
    identifiers_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    identifiers_parser.add_argument(
        "--ticket",
        help="Optional ticket override (defaults to docs/.active_ticket).",
    )
    identifiers_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override (defaults to docs/.active_feature).",
    )
    identifiers_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit identifiers as JSON for automation.",
    )
    identifiers_parser.set_defaults(func=_identifiers_command)

    set_active_stage_parser = subparsers.add_parser(
        "set-active-stage",
        help="Persist the active workflow stage in docs/.active_stage.",
    )
    set_active_stage_parser.add_argument(
        "stage",
        help=(
            "Stage name (idea/research/plan/review-plan/review-prd/"
            "tasklist/implement/review/qa)."
        ),
    )
    set_active_stage_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    set_active_stage_parser.add_argument(
        "--allow-custom",
        action="store_true",
        help="Allow arbitrary stage values (skip validation).",
    )
    set_active_stage_parser.set_defaults(func=_set_active_stage_command)

    prd_review_parser = subparsers.add_parser(
        "prd-review",
        help="Run lightweight PRD review heuristics and emit aidd/reports/prd/<ticket>.json.",
    )
    prd_review_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    prd_review_parser.add_argument(
        "--ticket",
        help="Feature ticket to analyse (defaults to docs/.active_ticket).",
    )
    prd_review_parser.add_argument(
        "--slug",
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override (defaults to docs/.active_feature when available).",
    )
    prd_review_parser.add_argument(
        "--prd",
        type=Path,
        help="Explicit path to PRD file. Defaults to docs/prd/<ticket>.prd.md.",
    )
    prd_review_parser.add_argument(
        "--report",
        type=Path,
        help="Optional path to store JSON report. Directories are created automatically.",
    )
    prd_review_parser.add_argument(
        "--emit-text",
        action="store_true",
        help="Print a human-readable summary in addition to JSON output.",
    )
    prd_review_parser.add_argument(
        "--stdout-format",
        choices=("json", "text", "auto"),
        default="auto",
        help="Format for stdout output (default: auto). Auto prints text when --emit-text is used.",
    )
    prd_review_parser.add_argument(
        "--emit-patch",
        action="store_true",
        help="Emit RFC6902 patch file when a previous report exists.",
    )
    prd_review_parser.add_argument(
        "--pack-only",
        action="store_true",
        help="Remove JSON report after writing pack sidecar.",
    )
    prd_review_parser.set_defaults(func=_prd_review_command)

    plan_review_gate_parser = subparsers.add_parser(
        "plan-review-gate",
        help="Validate plan review readiness (used by hooks).",
    )
    plan_review_gate_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    plan_review_gate_parser.add_argument("--ticket", required=True, help="Active feature ticket.")
    plan_review_gate_parser.add_argument("--file-path", default="", help="Path being modified.")
    plan_review_gate_parser.add_argument("--branch", default="", help="Current branch name.")
    plan_review_gate_parser.add_argument(
        "--config",
        default="config/gates.json",
        help="Path to gates configuration file (default: config/gates.json).",
    )
    plan_review_gate_parser.add_argument(
        "--skip-on-plan-edit",
        action="store_true",
        help="Return success when the plan file itself is being edited.",
    )
    plan_review_gate_parser.set_defaults(func=_plan_review_gate_command)

    prd_review_gate_parser = subparsers.add_parser(
        "prd-review-gate",
        help="Validate PRD review readiness (used by hooks).",
    )
    prd_review_gate_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    prd_review_gate_parser.add_argument(
        "--ticket",
        "--slug",
        dest="ticket",
        required=True,
        help="Active feature ticket (legacy alias: --slug).",
    )
    prd_review_gate_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        default="",
        help="Optional slug hint used for messaging (defaults to docs/.active_feature).",
    )
    prd_review_gate_parser.add_argument(
        "--file-path",
        default="",
        help="Path being modified (used to skip checks for direct PRD edits).",
    )
    prd_review_gate_parser.add_argument(
        "--branch",
        default="",
        help="Current branch name for branch-based filters.",
    )
    prd_review_gate_parser.add_argument(
        "--config",
        default="config/gates.json",
        help="Path to gates configuration file (default: config/gates.json).",
    )
    prd_review_gate_parser.add_argument(
        "--skip-on-prd-edit",
        action="store_true",
        help="Return success when the PRD file itself is being edited.",
    )
    prd_review_gate_parser.set_defaults(func=_prd_review_gate_command)

    tasklist_check_parser = subparsers.add_parser(
        "tasklist-check",
        help="Validate tasklist spec readiness (used by hooks).",
    )
    tasklist_check_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    tasklist_check_parser.add_argument(
        "--ticket",
        help="Feature ticket (defaults to docs/.active_ticket).",
    )
    tasklist_check_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        default=None,
        help="Optional slug hint override.",
    )
    tasklist_check_parser.add_argument(
        "--branch",
        default="",
        help="Current branch name for branch filters.",
    )
    tasklist_check_parser.add_argument(
        "--config",
        default="config/gates.json",
        help="Path to gates configuration file (default: config/gates.json).",
    )
    tasklist_check_parser.add_argument(
        "--quiet-ok",
        action="store_true",
        help="Suppress output when the check passes.",
    )
    tasklist_check_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print skip diagnostics when the gate is disabled.",
    )
    tasklist_check_parser.set_defaults(func=_tasklist_check_command)

    researcher_context_parser = subparsers.add_parser(
        "researcher-context",
        help="Run researcher context builder (pass through to module CLI).",
    )
    researcher_context_parser.add_argument(
        "forward_args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to the researcher context tool.",
    )
    researcher_context_parser.set_defaults(func=_researcher_context_command)

    context_gc_parser = subparsers.add_parser(
        "context-gc",
        help="Run context GC hooks (precompact/sessionstart/pretooluse/stop/userprompt).",
    )
    context_gc_parser.add_argument(
        "mode",
        choices=("precompact", "sessionstart", "pretooluse", "stop", "userprompt"),
        help="Context GC mode to execute.",
    )
    context_gc_parser.set_defaults(func=_context_gc_command)

    analyst_parser = subparsers.add_parser(
        "analyst-check",
        help="Validate the analyst dialog (Вопрос/Ответ) for the active feature PRD.",
    )
    analyst_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to validate (defaults to docs/.active_ticket).",
    )
    analyst_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override for messaging (defaults to docs/.active_feature if present).",
    )
    analyst_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    analyst_parser.add_argument(
        "--branch",
        help="Current Git branch used to evaluate config.gates analyst branch rules.",
    )
    analyst_parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Allow Status: BLOCKED without failing validation.",
    )
    analyst_parser.add_argument(
        "--no-ready-required",
        action="store_true",
        help="Skip enforcing Status: READY (useful mid-dialog).",
    )
    analyst_parser.add_argument(
        "--min-questions",
        type=int,
        help="Override minimum number of questions expected from analyst.",
    )
    analyst_parser.set_defaults(func=_analyst_check_command)

    research_check_parser = subparsers.add_parser(
        "research-check",
        help="Validate the Researcher report (docs/research + aidd/reports/research).",
    )
    research_check_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to validate (defaults to docs/.active_ticket).",
    )
    research_check_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override for messaging (defaults to docs/.active_feature if present).",
    )
    research_check_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    research_check_parser.add_argument(
        "--branch",
        help="Current Git branch used to evaluate config.gates researcher branch rules.",
    )
    research_check_parser.set_defaults(func=_research_check_command)

    research_parser = subparsers.add_parser(
        "research",
        help="Collect scope and context for the Researcher agent.",
    )
    research_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to analyse (defaults to docs/.active_ticket).",
    )
    research_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override used for templates and keywords (defaults to docs/.active_feature).",
    )
    research_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    research_parser.add_argument(
        "--config",
        help="Path to conventions JSON containing the researcher section (defaults to config/conventions.json).",
    )
    research_parser.add_argument(
        "--paths",
        help="Colon-separated list of additional paths to scan (overrides defaults from conventions).",
    )
    research_parser.add_argument(
        "--paths-relative",
        choices=("workspace", "aidd"),
        help="Treat relative paths as workspace-rooted (default) or under aidd/. When omitted, defaults to workspace if target is aidd.",
    )
    research_parser.add_argument(
        "--keywords",
        help="Comma-separated list of extra keywords to search for.",
    )
    research_parser.add_argument(
        "--note",
        dest="notes",
        action="append",
        help="Free-form note or @path to include in the context; use '-' to read stdin once.",
    )
    research_parser.add_argument(
        "--limit",
        type=int,
        default=24,
        help="Maximum number of code/document matches to capture (default: 24).",
    )
    research_parser.add_argument(
        "--output",
        help="Override output JSON path (default: aidd/reports/research/<ticket>-context.json).",
    )
    research_parser.add_argument(
        "--pack-only",
        action="store_true",
        help="Remove JSON report after writing pack sidecar.",
    )
    research_parser.add_argument(
        "--targets-only",
        action="store_true",
        help="Only refresh targets JSON; skip content scan and context export.",
    )
    research_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print context JSON to stdout without writing files (targets are still refreshed).",
    )
    research_parser.add_argument(
        "--deep-code",
        action="store_true",
        help="Collect code symbols/imports/tests for reuse candidates (without building call graph).",
    )
    research_parser.add_argument(
        "--reuse-only",
        action="store_true",
        help="Skip keyword matches and focus on reuse candidates in the output.",
    )
    research_parser.add_argument(
        "--langs",
        help="Comma-separated list of languages to scan for deep analysis (py,kt,kts,java).",
    )
    research_parser.add_argument(
        "--call-graph",
        action="store_true",
        help="Build call/import graph (supported languages via tree-sitter if available).",
    )
    research_parser.add_argument(
        "--graph-engine",
        choices=["auto", "none", "ts"],
        default="auto",
        help="Engine for call graph: auto (tree-sitter when available), none (disable), ts (force tree-sitter).",
    )
    research_parser.add_argument(
        "--graph-langs",
        help="Comma-separated list of languages for call graph (kt,kts,java; others ignored).",
    )
    research_parser.add_argument(
        "--graph-filter",
        help="Regex to keep only matching call graph edges (matches file/caller/callee). Defaults to ticket/keywords.",
    )
    research_parser.add_argument(
        "--graph-limit",
        type=int,
        default=_DEFAULT_GRAPH_LIMIT,
        help=f"Maximum number of call graph edges to keep in focused graph (default: {_DEFAULT_GRAPH_LIMIT}).",
    )
    research_parser.add_argument(
        "--no-template",
        action="store_true",
        help="Do not materialise docs/research/<ticket>.md from the template.",
    )
    research_parser.add_argument(
        "--auto",
        action="store_true",
        help="Automation-friendly mode for /idea-new integrations (warn on empty matches).",
    )
    research_parser.set_defaults(func=_research_command)

    reviewer_tests_parser = subparsers.add_parser(
        "reviewer-tests",
        help="Update reviewer test requirement marker for the active feature.",
    )
    reviewer_tests_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to use (defaults to docs/.active_ticket).",
    )
    reviewer_tests_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override for marker metadata.",
    )
    reviewer_tests_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    reviewer_tests_parser.add_argument(
        "--status",
        default="required",
        help="Tests state to store in the marker (default: required).",
    )
    reviewer_tests_parser.add_argument(
        "--note",
        help="Optional note stored alongside the reviewer marker.",
    )
    reviewer_tests_parser.add_argument(
        "--requested-by",
        help="Override requested_by field in the marker (defaults to $USER).",
    )
    reviewer_tests_parser.add_argument(
        "--clear",
        action="store_true",
        help="Remove the marker instead of updating it.",
    )
    reviewer_tests_parser.set_defaults(func=_reviewer_tests_command)

    review_report_parser = subparsers.add_parser(
        "review-report",
        help="Create/update review report with findings (stored in aidd/reports/reviewer/<ticket>.json).",
    )
    review_report_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to use (defaults to docs/.active_ticket).",
    )
    review_report_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override for report metadata.",
    )
    review_report_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    review_report_parser.add_argument(
        "--branch",
        help="Optional branch override for metadata.",
    )
    review_report_parser.add_argument(
        "--report",
        help="Optional report path override (default: aidd/reports/reviewer/<ticket>.json).",
    )
    review_report_parser.add_argument(
        "--findings",
        help="JSON list of findings or JSON object containing findings.",
    )
    review_report_parser.add_argument(
        "--findings-file",
        help="Path to JSON file containing findings list or full report payload.",
    )
    review_report_parser.add_argument(
        "--status",
        help="Review status label to store (ready|warn|blocked).",
    )
    review_report_parser.add_argument(
        "--summary",
        help="Optional summary for the review report.",
    )
    review_report_parser.set_defaults(func=_review_report_command)

    tasks_parser = subparsers.add_parser(
        "tasks-derive",
        help="Generate tasklist candidates from QA/Research/Review reports.",
    )
    tasks_parser.add_argument(
        "--source",
        choices=("qa", "research", "review"),
        required=True,
        help="Report source to derive tasks from.",
    )
    tasks_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to use (defaults to docs/.active_ticket).",
    )
    tasks_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override used for messaging.",
    )
    tasks_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    tasks_parser.add_argument(
        "--report",
        help="Optional report path override (default depends on --source).",
    )
    tasks_parser.add_argument(
        "--append",
        action="store_true",
        help="Preserve existing handoff block and append new items instead of replacing it.",
    )
    tasks_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned changes without modifying files.",
    )
    tasks_parser.add_argument(
        "--prefer-pack",
        action="store_true",
        help="Prefer *.pack.yaml for research reports when available.",
    )
    tasks_parser.set_defaults(func=_tasks_derive_command)

    context_pack_parser = subparsers.add_parser(
        "context-pack",
        help="Build a compact context pack from AIDD anchors.",
    )
    context_pack_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier (defaults to docs/.active_ticket).",
    )
    context_pack_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override (defaults to docs/.active_feature).",
    )
    context_pack_parser.add_argument(
        "--agent",
        required=True,
        help="Agent name used in the context pack filename.",
    )
    context_pack_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    context_pack_parser.add_argument(
        "--output",
        help="Optional output path override (default: aidd/reports/context/<ticket>-<agent>.md).",
    )
    context_pack_parser.set_defaults(func=_context_pack_command)

    index_parser = subparsers.add_parser(
        "index-sync",
        help="Generate/update derived ticket index (docs/index/<ticket>.yaml).",
    )
    index_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to index (defaults to docs/.active_ticket).",
    )
    index_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override (defaults to docs/.active_feature).",
    )
    index_parser.add_argument(
        "--slug",
        help="Optional slug override used in the index file.",
    )
    index_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    index_parser.add_argument(
        "--output",
        help="Optional output path override (default: docs/index/<ticket>.yaml).",
    )
    index_parser.set_defaults(func=_index_sync_command)

    status_parser = subparsers.add_parser(
        "status",
        help="Show summary for a ticket (index + recent events).",
    )
    status_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier (defaults to docs/.active_ticket).",
    )
    status_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override (defaults to docs/.active_feature).",
    )
    status_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    status_parser.add_argument(
        "--refresh",
        action="store_true",
        help="Rebuild index before showing status.",
    )
    status_parser.add_argument(
        "--events",
        type=int,
        default=5,
        help="Number of recent events to show (default: 5).",
    )
    status_parser.set_defaults(func=_status_command)

    tests_log_parser = subparsers.add_parser(
        "tests-log",
        help="Append entry to tests JSONL log (aidd/reports/tests/<ticket>.jsonl).",
    )
    tests_log_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier (defaults to docs/.active_ticket).",
    )
    tests_log_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override (defaults to docs/.active_feature).",
    )
    tests_log_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    tests_log_parser.add_argument(
        "--status",
        required=True,
        help="Status label for the test entry (pass|fail|skipped|...).",
    )
    tests_log_parser.add_argument(
        "--summary",
        default="",
        help="Optional summary string stored in details.summary.",
    )
    tests_log_parser.add_argument(
        "--details",
        default="",
        help="Optional JSON object with extra fields for details.",
    )
    tests_log_parser.add_argument(
        "--source",
        default="aidd tests-log",
        help="Optional source label stored in the log entry.",
    )
    tests_log_parser.set_defaults(func=_tests_log_command)

    qa_parser = subparsers.add_parser(
        "qa",
        help="Run QA agent and generate aidd/reports/qa/<ticket>.json.",
    )
    qa_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to use (defaults to docs/.active_ticket).",
    )
    qa_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override used for messaging.",
    )
    qa_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    qa_parser.add_argument(
        "--branch",
        help="Git branch name for logging (autodetected by default).",
    )
    qa_parser.add_argument(
        "--report",
        help="Path to JSON report (default: aidd/reports/qa/<ticket>.json).",
    )
    qa_parser.add_argument(
        "--block-on",
        help="Comma-separated severities treated as blockers (pass-through to qa-agent).",
    )
    qa_parser.add_argument(
        "--warn-on",
        help="Comma-separated severities treated as warnings (pass-through to qa-agent).",
    )
    qa_parser.add_argument(
        "--scope",
        action="append",
        help="Optional scope filters (pass-through to qa-agent).",
    )
    qa_parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="qa-agent output format (default: json).",
    )
    qa_parser.add_argument(
        "--emit-json",
        action="store_true",
        help="Emit JSON to stdout even in gate mode.",
    )
    qa_parser.add_argument(
        "--emit-patch",
        action="store_true",
        help="Emit RFC6902 patch file when a previous report exists.",
    )
    qa_parser.add_argument(
        "--pack-only",
        action="store_true",
        help="Remove JSON report after writing pack sidecar.",
    )
    qa_parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip QA test run (not recommended; override is respected in gate mode).",
    )
    qa_parser.add_argument(
        "--allow-no-tests",
        action="store_true",
        help="Allow QA to proceed without tests (or with skipped test commands).",
    )
    qa_parser.add_argument(
        "--gate",
        action="store_true",
        help="Gate mode: non-zero exit code on blocker severities.",
    )
    qa_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Gate mode without failing on blockers.",
    )
    qa_parser.set_defaults(func=_qa_command)

    progress_parser = subparsers.add_parser(
        "progress",
        help="Check that docs/tasklist/<ticket>.md has new completed items after code changes.",
    )
    progress_parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to check (defaults to docs/.active_ticket).",
    )
    progress_parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override used for messaging.",
    )
    progress_parser.add_argument(
        "--target",
        default=".",
        help="Workspace root (default: current; workflow lives in ./aidd).",
    )
    progress_parser.add_argument(
        "--branch",
        help="Git branch name used to evaluate skip_branches (autodetected by default).",
    )
    progress_parser.add_argument(
        "--source",
        choices=("manual", "implement", "qa", "review", "gate", "handoff"),
        default="manual",
        help="Context in which the check is executed (default: manual).",
    )
    progress_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit result as JSON for scripting.",
    )
    progress_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed lists of code changes and checkbox updates.",
    )
    progress_parser.set_defaults(func=_progress_command)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except subprocess.CalledProcessError as exc:
        # Propagate the same exit code but provide human-friendly output.
        parser.exit(exc.returncode, f"[aidd] command failed: {exc}\n")
    except Exception as exc:  # pragma: no cover - safety net
        parser.exit(1, f"[aidd] {exc}\n")
    if isinstance(result, int):
        return result
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

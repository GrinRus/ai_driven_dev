from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from tools import runtime


_TASK_ID_RE = re.compile(r"\bid:\s*([A-Za-z0-9_.:-]+)")
_TASK_ID_SIGNATURE_RE = re.compile(r"(,?\s*id:\s*[A-Za-z0-9_.:-]+)")
_TASK_START_RE = re.compile(r"^\s*-\s*\[[ xX]\]")


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


def _is_task_start(line: str) -> bool:
    return bool(_TASK_START_RE.match(line))


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
    if summary == "fail":
        task_id = f"qa-tests:{_stable_task_id('qa-tests', 'summary', summary)}"
        suffix = _format_task_suffix(report_label, task_id)
        tasks.append(f"- [ ] QA tests: {summary}{suffix}")
    if summary in {"skipped", "not-run"}:
        task_id = f"qa-tests:{_stable_task_id('qa-tests', summary)}"
        suffix = _format_task_suffix(report_label, task_id)
        tasks.append(f"- [ ] QA tests: запустить автотесты и приложить лог{suffix}")
    for entry in executed:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "").strip().lower()
        if status != "fail":
            continue
        command = str(entry.get("command") or "").strip()
        log_path = str(entry.get("log") or entry.get("log_path") or "").strip()
        task_id = f"qa-tests:{_stable_task_id('qa-tests', 'fail', command, log_path)}"
        details = f" — {command}" if command else ""
        suffix = _format_task_suffix(report_label, task_id)
        log_hint = f" (log: {log_path})" if log_path else ""
        tasks.append(f"- [ ] QA tests: устранить падение{details}{log_hint}{suffix}")
    if summary == "fail" and not tasks:
        task_id = f"qa-tests:{_stable_task_id('qa-tests', 'fail', 'summary')}"
        suffix = _format_task_suffix(report_label, task_id)
        tasks.append(f"- [ ] QA tests: устранить падения тестов{suffix}")
    return tasks


def _inflate_columnar(section: object) -> List[Dict]:
    if not isinstance(section, dict):
        return []
    cols = section.get("cols")
    rows = section.get("rows")
    if not isinstance(cols, list) or not isinstance(rows, list):
        return []
    items: List[Dict] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        record: Dict[str, object] = {}
        for idx, col in enumerate(cols):
            if idx >= len(row):
                break
            record[str(col)] = row[idx]
        if record:
            items.append(record)
    return items


def _derive_tasks_from_research_context(payload: Dict, report_label: str, *, reuse_limit: int = 5) -> List[str]:
    tasks: List[str] = []
    matches = payload.get("matches") or []
    if isinstance(matches, dict):
        matches = _inflate_columnar(matches)
    has_context = bool(matches)
    profile = payload.get("profile") if isinstance(payload, dict) else {}
    recommendations = []
    if isinstance(profile, dict):
        recommendations = profile.get("recommendations") or []
    if isinstance(recommendations, str):
        recommendations = [recommendations]
    if isinstance(recommendations, dict):
        recommendations = _inflate_columnar(recommendations)
    for item in recommendations:
        if isinstance(item, dict):
            text = str(item.get("title") or item.get("recommendation") or item.get("text") or "").strip()
        else:
            text = str(item).strip()
        if not text:
            continue
        task_id = f"research:{_stable_task_id('research', text)}"
        suffix = _format_task_suffix(report_label, task_id)
        tasks.append(f"- [ ] Research: {text}{suffix}")

    manual_notes = payload.get("manual_notes") or []
    if isinstance(manual_notes, str):
        manual_notes = [manual_notes]
    if isinstance(manual_notes, dict):
        manual_notes = _inflate_columnar(manual_notes)
    for item in manual_notes:
        text = str(item.get("note") if isinstance(item, dict) else item).strip()
        if not text:
            continue
        task_id = f"research:note:{_stable_task_id('research-note', text)}"
        suffix = _format_task_suffix(report_label, task_id)
        tasks.append(f"- [ ] Research note: {text}{suffix}")
    reuse_candidates = payload.get("reuse_candidates") or []
    if isinstance(reuse_candidates, dict):
        reuse_candidates = _inflate_columnar(reuse_candidates)
    reuse_candidates = [item for item in reuse_candidates if isinstance(item, dict)]
    if reuse_candidates:
        reuse_candidates = sorted(
            reuse_candidates,
            key=lambda item: (item.get("score") or 0, item.get("path") or ""),
            reverse=True,
        )
    reuse_candidates = reuse_candidates[:reuse_limit]

    if reuse_candidates:
        for item in reuse_candidates:
            path = str(item.get("path") or "").strip()
            if not path:
                continue
            score = item.get("score") or 0
            task_id = f"research:reuse:{_stable_task_id('research-reuse', path)}"
            suffix = _format_task_suffix(report_label, task_id)
            score_label = f" (score {score})" if score else ""
            tasks.append(f"- [ ] Reuse candidate: {path}{score_label}{suffix}")
    if not tasks and (has_context or reuse_candidates):
        task_id = _stable_task_id("research", report_label, "review")
        suffix = _format_task_suffix(report_label, f"research:{task_id}")
        tasks.append(f"- [ ] Research: проверить обновлённый контекст{suffix}")
    return tasks


def _derive_tasks_from_ast_grep_pack(payload: Dict, report_label: str) -> List[str]:
    tasks: List[str] = []
    rules = payload.get("rules") or []
    if not isinstance(rules, list):
        return tasks
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_id = str(rule.get("rule_id") or "").strip()
        examples = rule.get("examples") or []
        if not isinstance(examples, list) or not examples:
            continue
        example = examples[0] if isinstance(examples[0], dict) else {}
        path = str(example.get("path") or "").strip()
        line = example.get("line") or ""
        message = str(example.get("message") or "").strip()
        if not path:
            continue
        task_id = f"astgrep:{rule_id}:{path}:{line}"
        details = f" — {message}" if message else ""
        suffix = _format_task_suffix(report_label, task_id)
        tasks.append(f"- [ ] Research: ast-grep {rule_id} @ {path}:{line}{details}{suffix}")
    return tasks


def _derive_handoff_placeholder(source: str, ticket: str, report_label: str) -> List[str]:
    task_id = f"{source}:report-{_stable_task_id(source, report_label, ticket)}"
    suffix = _format_task_suffix(report_label, task_id)
    if source == "qa":
        return [f"- [ ] QA report: подтвердить отсутствие блокеров{suffix}"]
    if source == "review":
        return [f"- [ ] Review report: подтвердить отсутствие замечаний{suffix}"]
    return [f"- [ ] Research: обновить контекст перед следующей итерацией{suffix}"]


def _dedupe_tasks(tasks: Sequence[str]) -> List[str]:
    seen = set()
    deduped: List[str] = []
    for task in tasks:
        signature = _task_signature(task)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(task)
    return deduped


def _split_task_blocks(lines: Sequence[str]) -> List[List[str]]:
    blocks: List[List[str]] = []
    current: List[str] = []
    for line in lines:
        if _is_task_start(line):
            if current:
                blocks.append(current)
            current = [line]
            continue
        if current:
            current.append(line)
        elif line.strip():
            blocks.append([line])
    if current:
        blocks.append(current)
    return blocks


def _flatten_task_blocks(blocks: Sequence[Sequence[str]]) -> List[str]:
    return [line for block in blocks for line in block]


def _merge_handoff_tasks(existing: Sequence[str], new_tasks: Sequence[str], *, append: bool) -> List[str]:
    if not append:
        return list(new_tasks)

    merged_blocks = _split_task_blocks(existing)
    new_blocks = _split_task_blocks(new_tasks)
    by_id = {}
    by_signature = {}
    for idx, block in enumerate(merged_blocks):
        if not block or not _is_task_start(block[0]):
            continue
        task_id = _task_id_from_line(block[0])
        if task_id:
            by_id[task_id] = idx
        signature = _task_signature(block[0])
        if signature:
            by_signature[signature] = idx

    for block in new_blocks:
        if not block:
            continue
        header = block[0]
        task_id = _task_id_from_line(header) if _is_task_start(header) else None
        signature = _task_signature(header) if _is_task_start(header) else ""
        idx = None
        if task_id and task_id in by_id:
            idx = by_id[task_id]
        elif signature and signature in by_signature:
            idx = by_signature[signature]

        if idx is None:
            merged_blocks.append(block)
            idx = len(merged_blocks) - 1
        else:
            existing_block = merged_blocks[idx]
            if existing_block and len(block) == 1 and len(existing_block) > 1:
                merged_blocks[idx] = [block[0], *existing_block[1:]]
            else:
                merged_blocks[idx] = block

        if task_id:
            by_id[task_id] = idx
        if signature:
            by_signature[signature] = idx

    return _flatten_task_blocks(merged_blocks)


def _extract_handoff_block(lines: List[str], source: str) -> tuple[int, int, List[str]]:
    hint_label = f"handoff:{source}"
    start = -1
    end = -1
    for idx, line in enumerate(lines):
        if hint_label in line and line.strip().startswith("<!--"):
            start = idx
            break
    if start == -1:
        return -1, -1, []
    for idx in range(start + 1, len(lines)):
        if hint_label in lines[idx] and lines[idx].strip().endswith("-->"):
            end = idx + 1
            break
    if end == -1:
        end = start + 1
    return start, end, lines[start:end]


def _find_section(lines: List[str], candidates: Sequence[str]) -> tuple[int, Optional[str]]:
    if not candidates:
        return -1, None
    lowered = [line.strip().lower() for line in lines]
    for candidate in candidates:
        label = candidate.strip().lower()
        try:
            idx = lowered.index(label)
        except ValueError:
            continue
        return idx, candidate
    return -1, None


def _apply_handoff_tasks(
    text: str,
    *,
    source: str,
    report_label: str,
    tasks: Sequence[str],
    append: bool,
    section_candidates: Sequence[str],
) -> tuple[str, Optional[str], bool]:
    lines = text.splitlines()
    handoff_start, handoff_end, block = _extract_handoff_block(lines, source)
    block_lines = block[1:-1] if len(block) >= 2 else []
    new_tasks = _merge_handoff_tasks(block_lines, tasks, append=append)

    if handoff_start != -1:
        start_marker = block[0] if block else f"<!-- handoff:{source} start -->"
        end_marker = block[-1] if block else f"<!-- handoff:{source} end -->"
        new_block = [start_marker, *new_tasks, end_marker]
        new_lines = lines[:handoff_start] + new_block + lines[handoff_end:]
        new_text = "\n".join(new_lines)
        if not new_text.endswith("\n"):
            new_text += "\n"
        return new_text, None, new_text != text

    insert_at, heading_label = _find_section(lines, section_candidates)
    if insert_at == -1:
        insert_at = len(lines)
    else:
        insert_at += 1
        while insert_at < len(lines) and not lines[insert_at].strip():
            insert_at += 1
    start_marker = f"<!-- handoff:{source} start (source: {report_label}) -->"
    end_marker = f"<!-- handoff:{source} end -->"
    block_lines = [start_marker, *new_tasks, end_marker]
    new_lines = lines[:insert_at] + block_lines + lines[insert_at:]
    new_text = "\n".join(new_lines)
    if not new_text.endswith("\n"):
        new_text += "\n"
    changed = new_text != text
    return new_text, heading_label, changed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate tasklist candidates from QA/Research/Review reports.",
    )
    parser.add_argument(
        "--source",
        choices=("qa", "research", "review"),
        required=True,
        help="Report source to derive tasks from.",
    )
    parser.add_argument(
        "--ticket",
        dest="ticket",
        help="Ticket identifier to use (defaults to docs/.active_ticket).",
    )
    parser.add_argument(
        "--slug-hint",
        dest="slug_hint",
        help="Optional slug hint override used for messaging.",
    )
    parser.add_argument(
        "--report",
        help="Optional report path override (default depends on --source).",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Preserve existing handoff block and append new items instead of replacing it.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned changes without modifying files.",
    )
    parser.add_argument(
        "--prefer-pack",
        action="store_true",
        help="Prefer *.pack.yaml for research reports when available.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _, target = runtime.require_workflow_root()

    context = runtime.resolve_feature_context(
        target,
        ticket=getattr(args, "ticket", None),
        slug_hint=getattr(args, "slug_hint", None),
    )
    ticket = (context.resolved_ticket or "").strip()
    slug_hint = (context.slug_hint or ticket or "").strip()
    if not ticket:
        raise ValueError("feature ticket is required; pass --ticket or set docs/.active_ticket via /feature-dev-aidd:idea-new.")

    source = (args.source or "").strip().lower()
    default_report = {
        "qa": "aidd/reports/qa/{ticket}.json",
        "research": "aidd/reports/research/{ticket}-context.json",
    }.get(source)
    if source == "review":
        default_report = runtime.review_report_template(target)
    report_template = args.report or default_report
    if not report_template:
        raise ValueError("unsupported source; expected qa|research|review")

    def _fmt(text: str) -> str:
        return (
            text.replace("{ticket}", ticket)
            .replace("{slug}", slug_hint or ticket)
        )

    report_path = runtime.resolve_path_for_target(Path(_fmt(report_template)), target)

    def _env_truthy(value: str | None) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "y"}

    prefer_pack = bool(getattr(args, "prefer_pack", False) or _env_truthy(os.getenv("AIDD_PACK_FIRST")))

    def _load_with_pack(path: Path, *, prefer_pack_first: bool) -> tuple[Dict, str]:
        from tools.reports.loader import load_report_for_path

        payload, source_kind, report_paths = load_report_for_path(path, prefer_pack=prefer_pack_first)
        label_path = report_paths.pack_path if source_kind == "pack" else report_paths.json_path
        return payload, runtime.rel_path(label_path, target)

    is_pack_path = report_path.name.endswith(".pack.yaml") or report_path.name.endswith(".pack.toon")
    if source == "research" and (prefer_pack or is_pack_path or not report_path.exists()):
        payload, report_label = _load_with_pack(report_path, prefer_pack_first=True)
    elif source == "qa" and (is_pack_path or not report_path.exists()):
        payload, report_label = _load_with_pack(report_path, prefer_pack_first=True)
    else:
        report_label = runtime.rel_path(report_path, target)
        if not report_path.exists():
            raise FileNotFoundError(f"{source} report not found at {report_label}")
        payload = runtime.load_json_file(report_path)
    if source == "qa":
        derived_tasks = _derive_tasks_from_findings("QA", payload, report_label)
        derived_tasks.extend(_derive_tasks_from_tests(payload, report_label))
    elif source == "review":
        derived_tasks = _derive_tasks_from_findings("Review", payload, report_label)
    elif source == "research":
        derived_tasks = _derive_tasks_from_research_context(payload, report_label)
        for ext in (".pack.yaml", ".pack.toon"):
            ast_pack = target / "reports" / "research" / f"{ticket}-ast-grep{ext}"
            if not ast_pack.exists():
                continue
            ast_payload = runtime.load_json_file(ast_pack)
            derived_tasks.extend(_derive_tasks_from_ast_grep_pack(ast_payload, runtime.rel_path(ast_pack, target)))
            break
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
            f"tasklist not found at {tasklist_rel}; create it via /feature-dev-aidd:tasks-new {ticket}."
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
    runtime.maybe_sync_index(target, ticket, slug_hint or None, reason="tasks-derive")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

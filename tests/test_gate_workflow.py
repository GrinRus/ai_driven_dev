import datetime as dt
import json
import pathlib
from pathlib import Path
import subprocess
from textwrap import dedent

from .helpers import (
    HOOKS_DIR,
    ensure_gates_config,
    ensure_project_root,
    git_config_user,
    git_init,
    run_hook,
    tasklist_ready_text,
    write_active_feature,
    write_active_stage,
    write_file,
    write_json,
    write_spec_ready,
    write_tasklist_ready,
)

SRC_PAYLOAD = '{"tool_input":{"file_path":"src/main/kotlin/App.kt"}}'
DOC_PAYLOAD = '{"tool_input":{"file_path":"docs/prd/demo-checkout.prd.md"}}'
PROMPT_PAYLOAD = '{"tool_input":{"file_path":"agents/analyst.md"}}'
CMD_PAYLOAD = '{"tool_input":{"file_path":"commands/plan-new.md"}}'
AIDD_SRC_PAYLOAD = '{"tool_input":{"file_path":"aidd/src/main/kotlin/App.kt"}}'
IDEA_PAYLOAD = '{"tool_input":{"file_path":"src/main/kotlin/App.kt","ticket":"demo-thin"}}'
PROMPT_PAIRS = [
    ("analyst", "idea-new"),
    ("planner", "plan-new"),
    ("plan-reviewer", "review-spec"),
    ("implementer", "implement"),
    ("reviewer", "review"),
    ("researcher", "researcher"),
    ("prd-reviewer", "review-spec"),
]
REVIEW_REPORT = {"summary": "", "findings": []}


def append_handoff(tasklist_path: Path, content: str) -> None:
    text = tasklist_path.read_text(encoding="utf-8")
    marker = "<!-- handoff:manual end -->"
    insert = content.rstrip("\n") + "\n"
    if marker in text:
        text = text.replace(marker, f"{insert}{marker}", 1)
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += insert
    tasklist_path.write_text(text, encoding="utf-8")


def _plugin_hooks():
    path = HOOKS_DIR / "hooks.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _has_command(hooks: dict, event: str, needle: str) -> bool:
    return any(
        needle in hook.get("command", "")
        for entry in hooks.get("hooks", {}).get(event, [])
        for hook in entry.get("hooks", [])
    )


def _timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def approved_prd(ticket: str = "demo-checkout") -> str:
    return (
        "# PRD\n\n"
        "## Диалог analyst\n"
        "Status: READY\n\n"
        f"Researcher: docs/research/{ticket}.md (Status: reviewed)\n\n"
        "Вопрос 1: Требуется ли отдельный сценарий оплаты?\n"
        "Ответ 1: Покрываем happy-path и отказ платежа.\n\n"
        "## PRD Review\n"
        "Status: READY\n"
    )


def pending_baseline_prd(ticket: str = "demo-checkout") -> str:
    return (
        "# PRD\n\n"
        "## Диалог analyst\n"
        "Status: READY\n\n"
        f"Researcher: docs/research/{ticket}.md (Status: pending)\n\n"
        "Вопрос 1: Что нужно для baseline?\n"
        "Ответ 1: Репозиторий пуст, собираем baseline.\n\n"
        "## PRD Review\n"
        "Status: READY\n"
    )


def write_research_doc(
    tmp_path: pathlib.Path,
    ticket: str = "demo-checkout",
    status: str = "reviewed",
    rlm_status: str = "ready",
) -> None:
    from datetime import datetime, timezone

    generated_at = datetime.now(timezone.utc).isoformat()
    src_path = tmp_path / "src" / "main" / "kotlin" / "App.kt"
    if not src_path.exists():
        src_path.parent.mkdir(parents=True, exist_ok=True)
        src_path.write_text("class App\n", encoding="utf-8")
    write_file(
        tmp_path,
        f"docs/research/{ticket}.md",
        f"# Research\n\nStatus: {status}\n",
    )
    write_json(
        tmp_path,
        f"reports/research/{ticket}-targets.json",
        {"paths": ["src/main/kotlin"], "docs": [f"docs/research/{ticket}.md"]},
    )
    write_json(
        tmp_path,
        f"reports/research/{ticket}-context.json",
        {
            "status": status,
            "generated_at": generated_at,
            "profile": {},
            "manual_notes": [],
            "matches": [],
            "targets": {"paths": ["src/main/kotlin"]},
            "rlm_status": rlm_status,
            "rlm_targets_path": f"reports/research/{ticket}-rlm-targets.json",
            "rlm_manifest_path": f"reports/research/{ticket}-rlm-manifest.json",
            "rlm_worklist_path": f"reports/research/{ticket}-rlm.worklist.pack.json",
            "rlm_nodes_path": f"reports/research/{ticket}-rlm.nodes.jsonl",
            "rlm_links_path": f"reports/research/{ticket}-rlm.links.jsonl",
            "rlm_pack_path": f"reports/research/{ticket}-rlm.pack.json",
        },
    )
    write_json(
        tmp_path,
        f"reports/research/{ticket}-ast-grep.pack.json",
        {
            "type": "ast-grep",
            "kind": "pack",
            "rules": [
                {
                    "rule_id": "jvm.spring.rest",
                    "examples": [
                        {
                            "path": "src/main/kotlin/App.kt",
                            "line": 3,
                            "message": "REST endpoint",
                        }
                    ],
                }
            ],
        },
    )
    write_json(
        tmp_path,
        f"reports/research/{ticket}-rlm-targets.json",
        {"ticket": ticket, "files": ["src/main/kotlin/App.kt"], "generated_at": generated_at},
    )
    write_json(
        tmp_path,
        f"reports/research/{ticket}-rlm-manifest.json",
        {
            "ticket": ticket,
            "files": [
                {
                    "file_id": "file-app",
                    "path": "src/main/kotlin/App.kt",
                    "rev_sha": "rev-app",
                    "lang": "kt",
                    "size": 10,
                    "prompt_version": "v1",
                }
            ],
        },
    )
    worklist_payload = {
        "schema": "aidd.report.pack.v1",
        "type": "rlm-worklist",
        "status": "pending",
    }
    if rlm_status == "ready":
        worklist_payload["status"] = "ready"
        worklist_payload["entries"] = []
    write_json(
        tmp_path,
        f"reports/research/{ticket}-rlm.worklist.pack.json",
        worklist_payload,
    )
    if rlm_status == "ready":
        write_file(
            tmp_path,
            f"reports/research/{ticket}-rlm.nodes.jsonl",
            '{"node_kind":"file","file_id":"file-app","id":"file-app","path":"src/main/kotlin/App.kt","rev_sha":"rev-app"}\n',
        )
        write_file(
            tmp_path,
            f"reports/research/{ticket}-rlm.links.jsonl",
            '{"link_id":"link-1","src_file_id":"file-app","dst_file_id":"file-app","type":"calls","evidence_ref":{"path":"src/main/kotlin/App.kt","line_start":1,"line_end":1,"extractor":"regex","match_hash":"hash"},"unverified":false}\n',
        )
        write_json(
            tmp_path,
            f"reports/research/{ticket}-rlm.pack.json",
            {"schema": "aidd.report.pack.v1", "type": "rlm", "status": "ready"},
        )


def write_prd_with_status(tmp_path: pathlib.Path, ticket: str, status: str, research_status: str = "pending") -> None:
    write_file(
        tmp_path,
        f"docs/prd/{ticket}.prd.md",
        (
            "# PRD\n\n"
            "## Диалог analyst\n"
            f"Status: {status}\n\n"
            f"Researcher: docs/research/{ticket}.md (Status: {research_status})\n\n"
            "Вопрос 1: Что нужно уточнить?\n"
            "Ответ 1: TBD\n\n"
            "## PRD Review\n"
            "Status: READY\n"
        ),
    )


def write_plan_with_review(tmp_path: pathlib.Path, ticket: str = "demo-checkout", status: str = "READY") -> None:
    write_file(
        tmp_path,
        f"docs/plan/{ticket}.md",
        (
            "# Plan\n\n"
            "## Plan Review\n"
            f"Status: {status}\n\n"
            "## AIDD:ITERATIONS\n"
            "- iteration_id: I1\n"
            "  - Goal: bootstrap\n"
            "- iteration_id: I2\n"
            "  - Goal: follow-up\n"
            "- iteration_id: I3\n"
            "  - Goal: follow-up\n"
        ),
    )


def test_no_active_feature_allows_changes(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_missing_prd_blocks_when_feature_active(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, "demo-checkout")
    write_plan_with_review(tmp_path)
    write_file(
        tmp_path,
        "docs/tasklist/demo-checkout.md",
        "- [ ] <ticket> placeholder\n",
    )
    write_spec_ready(tmp_path, "demo-checkout")

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert (
        "нет PRD" in result.stdout
        or "нет PRD" in result.stderr
        or "не содержит раздела `## Диалог analyst`" in result.stderr
    )


def test_missing_plan_blocks(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, "demo-checkout")
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", approved_prd())
    write_json(tmp_path, "reports/prd/demo-checkout.json", REVIEW_REPORT)
    write_research_doc(tmp_path)

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "нет плана" in result.stdout or "нет плана" in result.stderr


def test_tasklist_blocks_when_next3_missing_fields(tmp_path):
    ticket = "demo-checkout"
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, ticket)
    write_active_stage(tmp_path, "review")
    write_file(tmp_path, f"docs/prd/{ticket}.prd.md", approved_prd(ticket))
    write_json(tmp_path, f"reports/prd/{ticket}.json", REVIEW_REPORT)
    write_plan_with_review(tmp_path, ticket)
    write_research_doc(tmp_path, ticket=ticket, status="reviewed")
    tasklist_path = write_tasklist_ready(tmp_path, ticket)
    text = tasklist_path.read_text(encoding="utf-8")
    text = text.replace("DoD: tasklist ready", "DoD:", 1)
    tasklist_path.write_text(text, encoding="utf-8")
    append_handoff(tasklist_path, f"- [ ] Research handoff (source: aidd/reports/research/{ticket}-context.json)\n")

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    combined = (result.stdout + result.stderr).lower()
    assert "next_3" in combined or "dod" in combined or "boundaries" in combined


def test_tasklist_blocks_when_test_execution_missing(tmp_path):
    ticket = "demo-checkout"
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, ticket)
    write_active_stage(tmp_path, "review")
    write_file(tmp_path, f"docs/prd/{ticket}.prd.md", approved_prd(ticket))
    write_json(tmp_path, f"reports/prd/{ticket}.json", REVIEW_REPORT)
    write_plan_with_review(tmp_path, ticket)
    write_research_doc(tmp_path, ticket=ticket, status="reviewed")
    tasklist_path = write_tasklist_ready(tmp_path, ticket)
    text = tasklist_path.read_text(encoding="utf-8")
    text = text.replace("- profile: none\n", "", 1)
    tasklist_path.write_text(text, encoding="utf-8")
    append_handoff(tasklist_path, f"- [ ] Research handoff (source: aidd/reports/research/{ticket}-context.json)\n")

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    combined = (result.stdout + result.stderr).lower()
    assert "test_execution" in combined or "profile" in combined


def test_tasklist_blocks_when_plan_iteration_missing_in_tasklist(tmp_path):
    ticket = "demo-checkout"
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, ticket)
    write_active_stage(tmp_path, "review")
    write_file(tmp_path, f"docs/prd/{ticket}.prd.md", approved_prd(ticket))
    write_json(tmp_path, f"reports/prd/{ticket}.json", REVIEW_REPORT)
    write_plan_with_review(tmp_path, ticket)
    plan_path = ensure_project_root(tmp_path) / "docs" / "plan" / f"{ticket}.md"
    with plan_path.open("a", encoding="utf-8") as fh:
        fh.write("- iteration_id: I4\n  - Goal: extra scope\n")
    write_research_doc(tmp_path, ticket=ticket, status="reviewed")
    tasklist_path = write_tasklist_ready(tmp_path, ticket)
    append_handoff(tasklist_path, f"- [ ] Research handoff (source: aidd/reports/research/{ticket}-context.json)\n")

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    combined = (result.stdout + result.stderr).lower()
    assert "iteration_id" in combined or "missing iteration" in combined


def test_pending_baseline_allows_docs_only(tmp_path):
    ticket = "demo-checkout"
    write_active_feature(tmp_path, ticket)
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", pending_baseline_prd(ticket))
    write_json(tmp_path, "reports/prd/demo-checkout.json", REVIEW_REPORT)
    write_plan_with_review(tmp_path)
    write_file(tmp_path, "docs/tasklist/demo-checkout.md", "- [ ] <ticket> placeholder\n")
    write_spec_ready(tmp_path, ticket)
    write_research_doc(tmp_path, status="pending")
    write_json(
        tmp_path,
        f"reports/research/{ticket}-context.json",
        {
            "ticket": ticket,
            "generated_at": _timestamp(),
            "profile": {"is_new_project": True},
            "auto_mode": True,
            "matches": [],
            "targets": {"paths": [], "docs": []},
        },
    )
    write_json(
        tmp_path,
        f"reports/research/{ticket}-targets.json",
        {"paths": [], "docs": [], "generated_at": _timestamp()},
    )
    # doc-only change: should allow pending baseline
    result = run_hook(tmp_path, "gate-workflow.sh", DOC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_research_required_then_passes_after_report(tmp_path):
    ticket = "demo-checkout"
    write_active_feature(tmp_path, ticket)
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_prd_with_status(tmp_path, ticket, status="READY", research_status="pending")
    write_plan_with_review(tmp_path, ticket)
    tasklist_path = write_tasklist_ready(tmp_path, ticket)
    write_json(tmp_path, f"reports/prd/{ticket}.json", REVIEW_REPORT)
    ensure_gates_config(
        tmp_path,
        {
            "researcher": {
                "enabled": True,
                "require_status": ["reviewed"],
                "allow_missing": False,
                "minimum_paths": 1,
                "allow_pending_baseline": False,
            }
        },
    )

    # Missing research report should block
    result_block = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result_block.returncode == 2

    # Add research report + context and expect pass
    write_research_doc(tmp_path, ticket=ticket, status="reviewed")
    write_json(
        tmp_path,
        f"reports/research/{ticket}-context.json",
        {
            "ticket": ticket,
            "generated_at": _timestamp(),
            "profile": {},
            "auto_mode": False,
        },
    )
    write_json(
        tmp_path,
        f"reports/research/{ticket}-targets.json",
        {"paths": ["src/main/kotlin"], "docs": [f"docs/research/{ticket}.md"]},
    )
    # add research handoff marker to tasklist to satisfy gate handoff check
    append_handoff(tasklist_path, f"- [ ] Research handoff (source: aidd/reports/research/{ticket}-context.json)\n")

    result_ok = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result_ok.returncode == 0, result_ok.stderr


def test_autodetects_aidd_root_with_ready_prd_and_research(tmp_path):
    ticket = "demo-checkout"
    project_root = tmp_path / "aidd"
    write_file(project_root, "src/main/kotlin/App.kt", "class App")
    write_active_feature(project_root, ticket)
    write_file(project_root, f"docs/prd/{ticket}.prd.md", approved_prd(ticket))
    write_plan_with_review(project_root, ticket)
    write_tasklist_ready(project_root, ticket)
    write_json(project_root, f"reports/prd/{ticket}.json", REVIEW_REPORT)
    write_research_doc(project_root, ticket=ticket, status="reviewed")
    write_json(
        project_root,
        f"reports/research/{ticket}-targets.json",
        {"paths": ["src/main/kotlin"], "docs": [f"docs/research/{ticket}.md"]},
    )
    write_json(
        project_root,
        f"reports/research/{ticket}-context.json",
        {
            "ticket": ticket,
            "generated_at": _timestamp(),
            "profile": {},
            "auto_mode": False,
        },
    )
    append_handoff(
        project_root / f"docs/tasklist/{ticket}.md",
        f"- [ ] Research handoff (source: aidd/reports/research/{ticket}-context.json)\n",
    )
    result = run_hook(tmp_path, "gate-workflow.sh", AIDD_SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_prd_draft_blocks_even_with_reviewed_research(tmp_path):
    ticket = "demo-draft"
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, ticket)
    write_file(
        tmp_path,
        f"docs/prd/{ticket}.prd.md",
        (
            "# PRD\n\n"
            "## Диалог analyst\n"
            "Status: draft\n\n"
            f"Researcher: docs/research/{ticket}.md (Status: reviewed)\n\n"
            "Вопрос 1: Какие ограничения?\n"
            "Ответ 1: TBD\n\n"
            "## PRD Review\n"
            "Status: READY\n"
        ),
    )
    write_plan_with_review(tmp_path, ticket)
    write_file(tmp_path, f"docs/tasklist/{ticket}.md", "- [ ] clarify limits\n")
    write_spec_ready(tmp_path, ticket)
    write_json(tmp_path, f"reports/prd/{ticket}.json", REVIEW_REPORT)
    write_research_doc(tmp_path, ticket=ticket, status="reviewed")
    write_json(
        tmp_path,
        f"reports/research/{ticket}-targets.json",
        {"paths": ["src/main/kotlin"], "docs": [f"docs/research/{ticket}.md"]},
    )
    write_json(
        tmp_path,
        f"reports/research/{ticket}-context.json",
        {"ticket": ticket, "generated_at": _timestamp(), "profile": {}, "status": "reviewed"},
    )

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    combined = (result.stdout + result.stderr).lower()
    assert "draft" in combined or "готов" in combined


def test_idea_new_flow_creates_active_in_aidd_and_blocks_until_ready(tmp_path):
    ticket = "demo-thin"
    project_root = tmp_path / "aidd"
    write_file(project_root, "src/main/kotlin/App.kt", "class App")
    # emulate idea-new: set active, scaffold PRD/research stub
    write_file(project_root, "docs/.active_ticket", ticket)
    write_file(project_root, "docs/.active_feature", "thin context demo")
    write_file(project_root, f"docs/prd/{ticket}.prd.md", approved_prd(ticket))
    write_plan_with_review(project_root, ticket)
    write_tasklist_ready(project_root, ticket)
    write_file(project_root, f"docs/research/{ticket}.md", "# Research\nStatus: pending\n")
    write_json(project_root, f"reports/research/{ticket}-targets.json", {"paths": ["src/main/kotlin"], "docs": []})
    write_json(project_root, f"reports/research/{ticket}-context.json", {"ticket": ticket, "generated_at": _timestamp(), "profile": {}})
    write_json(project_root, f"reports/prd/{ticket}.json", REVIEW_REPORT)
    # missing reviewed research -> should block
    result_block = run_hook(tmp_path, "gate-workflow.sh", IDEA_PAYLOAD)
    assert result_block.returncode == 2

    # after research reviewed -> should pass
    write_research_doc(project_root, ticket=ticket, status="reviewed")
    append_handoff(
        project_root / f"docs/tasklist/{ticket}.md",
        f"- [ ] Research handoff (source: aidd/reports/research/{ticket}-context.json)\n",
    )

    result_ok = run_hook(tmp_path, "gate-workflow.sh", IDEA_PAYLOAD)
    assert result_ok.returncode == 0, result_ok.stderr


def test_idea_new_rich_context_allows_ready_without_auto_research(tmp_path):
    ticket = "demo-rich"
    project_root = tmp_path / "aidd"
    write_file(project_root, "src/main/kotlin/App.kt", "class App")
    write_file(project_root, "docs/.active_ticket", ticket)
    write_file(project_root, "docs/.active_feature", "rich context demo")
    write_file(
        project_root,
        f"docs/prd/{ticket}.prd.md",
        (
            "# PRD\n\n"
            "## Диалог analyst\n"
            "Status: READY\n\n"
            "Researcher: docs/research/demo-rich.md (Status: reviewed)\n\n"
            "Вопрос 1: Какие требования уже покрыты?\n"
            "Ответ 1: Достаточно контекста, research не запускали.\n\n"
            "## PRD Review\n"
            "Status: READY\n"
        ),
    )
    write_plan_with_review(project_root, ticket)
    write_tasklist_ready(project_root, ticket)
    append_handoff(
        project_root / f"docs/tasklist/{ticket}.md",
        "- [ ] Research handoff (source: aidd/reports/research/demo-rich-context.json)\n",
    )
    write_file(project_root, f"docs/research/{ticket}.md", "# Research\nStatus: reviewed\n")
    write_json(project_root, f"reports/prd/{ticket}.json", REVIEW_REPORT)
    write_research_doc(project_root, ticket=ticket, status="reviewed")
    write_json(
        project_root,
        f"reports/reviewer/{ticket}/{ticket}.tests.json",
        {"ticket": ticket, "tests": "optional"},
    )
    result = run_hook(tmp_path, "gate-workflow.sh", IDEA_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_research_required_before_code_changes(tmp_path):
    ticket = "demo-checkout"
    write_active_feature(tmp_path, ticket)
    # PRD drafted but research missing → gate should block code edits
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", pending_baseline_prd(ticket))
    write_json(tmp_path, "reports/prd/demo-checkout.json", REVIEW_REPORT)
    write_plan_with_review(tmp_path)
    write_file(tmp_path, "docs/tasklist/demo-checkout.md", "- [ ] <ticket> placeholder\n")
    write_spec_ready(tmp_path, ticket)

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    combined = (result.stdout + result.stderr).lower()
    assert "research" in combined or "отчёт" in combined

    # After research is added (reviewed) and tasklist has real items, code edits should be allowed
    write_research_doc(tmp_path, status="reviewed")
    write_file(
        tmp_path,
        "docs/tasklist/demo-checkout.md",
        "- [ ] initial task\n- [ ] second task\n",
    )
    write_json(
        tmp_path,
        "reports/reviewer/demo-checkout/demo-checkout.tests.json",
        {"ticket": ticket, "tests": "optional"},
    )
    write_json(
        tmp_path,
        "reports/research/demo-checkout-context.json",
        {"ticket": ticket, "generated_at": _timestamp(), "profile": {}, "matches": [], "targets": {"paths": ["src"], "docs": ["docs"]}},
    )
    write_json(
        tmp_path,
        "reports/research/demo-checkout-targets.json",
        {"paths": ["src"], "docs": ["docs"], "generated_at": _timestamp()},
    )
    tasklist_path = write_tasklist_ready(tmp_path, ticket)
    append_handoff(
        tasklist_path,
        "<!-- handoff:research start (source: aidd/reports/research/demo-checkout-context.json) -->\n"
        "- [ ] add research handoff\n"
        "<!-- handoff:research end -->\n",
    )
    result_ok = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result_ok.returncode == 0, result_ok.stderr


def test_blocked_status_blocks(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, "demo-checkout")
    blocked_prd = (
        "# PRD\n\n"
        "## Диалог analyst\n"
        "Status: BLOCKED\n\n"
        "Researcher: docs/research/demo-checkout.md (Status: pending)\n\n"
        "Вопрос 1: Требуется ли отдельный сценарий оплаты?\n"
        "Ответ 1: Нужен список кейсов, уточнение в процессе.\n\n"
        "## PRD Review\n"
        "Status: pending\n"
    )
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", blocked_prd)
    write_json(tmp_path, "reports/prd/demo-checkout.json", REVIEW_REPORT)
    write_research_doc(tmp_path)
    write_plan_with_review(tmp_path)
    write_file(
        tmp_path,
        "docs/tasklist/demo-checkout.md",
        "- [ ] <ticket> placeholder\n",
    )
    write_spec_ready(tmp_path, "demo-checkout")

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "Status" in result.stdout or "Status" in result.stderr


def test_missing_tasks_blocks(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, "demo-checkout")
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", approved_prd())
    write_plan_with_review(tmp_path)
    write_json(tmp_path, "reports/prd/demo-checkout.json", REVIEW_REPORT)
    write_research_doc(tmp_path)

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "нет задач" in result.stdout or "нет задач" in result.stderr


def test_tasks_with_slug_allow_changes(tmp_path):
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, "demo-checkout")
    write_file(tmp_path, "docs/prd/demo-checkout.prd.md", approved_prd())
    write_plan_with_review(tmp_path)
    write_json(tmp_path, "reports/prd/demo-checkout.json", REVIEW_REPORT)
    write_research_doc(tmp_path)
    write_json(
        tmp_path,
        "reports/reviewer/demo-checkout/demo-checkout.tests.json",
        {"ticket": "demo-checkout", "tests": "optional"},
    )
    tasklist_path = write_tasklist_ready(tmp_path, "demo-checkout")
    append_handoff(
        tasklist_path,
        "<!-- handoff:research start (source: aidd/reports/research/demo-checkout-context.json) -->\n"
        "- [ ] Research: follow-up\n"
        "<!-- handoff:research end -->\n",
    )

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_review_handoff_blocks_without_tasklist_entry(tmp_path):
    ticket = "demo-review"
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, ticket)
    write_file(tmp_path, f"docs/prd/{ticket}.prd.md", approved_prd(ticket))
    write_plan_with_review(tmp_path, ticket)
    write_json(tmp_path, f"reports/prd/{ticket}.json", REVIEW_REPORT)
    write_research_doc(tmp_path, ticket)
    write_json(
        tmp_path,
        f"reports/reviewer/{ticket}/{ticket}.json",
        {
            "kind": "review",
            "status": "WARN",
            "findings": [{"severity": "major", "title": "Edge case", "recommendation": "Handle error"}],
        },
    )
    tasklist_path = write_tasklist_ready(tmp_path, ticket)
    append_handoff(
        tasklist_path,
        f"<!-- handoff:research start (source: aidd/reports/research/{ticket}-context.json) -->\n"
        "- [ ] Research: follow-up\n"
        "<!-- handoff:research end -->\n",
    )

    result_block = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result_block.returncode == 2
    combined = result_block.stdout + result_block.stderr
    assert "handoff" in combined.lower()

    tasklist_path = write_tasklist_ready(tmp_path, ticket)
    append_handoff(
        tasklist_path,
        f"<!-- handoff:research start (source: aidd/reports/research/{ticket}-context.json) -->\n"
        "- [ ] Research: follow-up\n"
        "<!-- handoff:research end -->\n"
        f"<!-- handoff:review start (source: aidd/reports/reviewer/{ticket}/{ticket}.json) -->\n"
        "- [ ] Review: fix edge case\n"
        "<!-- handoff:review end -->\n",
    )

    result_ok = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result_ok.returncode == 0, result_ok.stderr


def test_review_handoff_blocks_on_empty_report(tmp_path):
    ticket = "demo-review-empty"
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, ticket)
    write_file(tmp_path, f"docs/prd/{ticket}.prd.md", approved_prd(ticket))
    write_plan_with_review(tmp_path, ticket)
    write_json(tmp_path, f"reports/prd/{ticket}.json", REVIEW_REPORT)
    write_research_doc(tmp_path, ticket)
    write_json(
        tmp_path,
        f"reports/reviewer/{ticket}/{ticket}.json",
        {
            "kind": "review",
            "stage": "review",
            "status": "READY",
            "findings": [],
        },
    )
    tasklist_path = write_tasklist_ready(tmp_path, ticket)
    append_handoff(
        tasklist_path,
        f"<!-- handoff:research start (source: aidd/reports/research/{ticket}-context.json) -->\n"
        "- [ ] Research: follow-up\n"
        "<!-- handoff:research end -->\n",
    )

    result_block = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result_block.returncode == 2
    combined = result_block.stdout + result_block.stderr
    assert "handoff" in combined.lower()

    tasklist_path = write_tasklist_ready(tmp_path, ticket)
    append_handoff(
        tasklist_path,
        f"<!-- handoff:research start (source: aidd/reports/research/{ticket}-context.json) -->\n"
        "- [ ] Research: follow-up\n"
        "<!-- handoff:research end -->\n"
        f"<!-- handoff:review start (source: aidd/reports/reviewer/{ticket}/{ticket}.json) -->\n"
        f"- [ ] Review report: подтвердить отсутствие замечаний (source: aidd/reports/reviewer/{ticket}/{ticket}.json, id: review:report-1234567890ab)\n"
        "<!-- handoff:review end -->\n",
    )

    result_ok = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result_ok.returncode == 0, result_ok.stderr


def test_handoff_uses_configured_qa_report(tmp_path):
    ticket = "demo-qa-custom"
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    ensure_gates_config(
        tmp_path,
        {
            "prd_review": {"enabled": False},
            "plan_review": {"enabled": False},
            "researcher": {"enabled": False},
            "analyst": {"enabled": False},
            "reviewer": {"enabled": False},
            "qa": {"report": "aidd/reports/qa/custom/{ticket}.json"},
        },
    )
    write_active_feature(tmp_path, ticket)
    write_file(tmp_path, f"docs/prd/{ticket}.prd.md", approved_prd(ticket))
    write_plan_with_review(tmp_path, ticket)
    write_json(tmp_path, f"reports/qa/custom/{ticket}.json", {"status": "READY", "findings": []})
    tasklist_path = write_tasklist_ready(tmp_path, ticket)
    append_handoff(
        tasklist_path,
        f"<!-- handoff:qa start (source: aidd/reports/qa/custom/{ticket}.json) -->\n"
        f"- [ ] QA report: подтвердить отсутствие блокеров (source: aidd/reports/qa/custom/{ticket}.json, id: qa:report-1234567890ab)\n"
        "<!-- handoff:qa end -->\n",
    )

    result = run_hook(
        tmp_path,
        "gate-workflow.sh",
        SRC_PAYLOAD,
        extra_env={"CLAUDE_SKIP_TASKLIST_PROGRESS": "1"},
    )
    assert result.returncode == 0, result.stderr


def test_plugin_hooks_cover_workflow_events():
    hooks = _plugin_hooks()
    assert _has_command(hooks, "Stop", "gate-workflow.sh"), "gate-workflow missing in Stop"
    for event, entries in hooks.get("hooks", {}).items():
        for entry in entries:
            for hook in entry.get("hooks", []):
                cmd = hook.get("command", "")
                assert "${CLAUDE_PLUGIN_ROOT}" in cmd, f"hook command missing aidd guard in {event}: {cmd}"


def _ru_prompt(version: str, name: str = "analyst") -> str:
    text = dedent(
        f"""
        ---
        name: {name}
        description: test
        lang: ru
        prompt_version: {version}
        source_version: {version}
        tools: Read
        model: inherit
        ---

        ## Контекст
        text

        ## Входные артефакты
        - item

        ## Автоматизация
        text

        ## Пошаговый план
        1. step

        ## Fail-fast и вопросы
        text

        ## Формат ответа
        text
        """
    ).strip() + "\n"
    return text


def _ru_command(version: str, name: str = "plan-new") -> str:
    text = dedent(
        f"""
        ---
        description: "{name}"
        argument-hint: "<TICKET>"
        lang: ru
        prompt_version: {version}
        source_version: {version}
        allowed-tools: Read
        model: inherit
        ---

        ## Контекст
        text

        ## Входные артефакты
        - item

        ## Когда запускать
        text

        ## Автоматические хуки и переменные
        text

        ## Что редактируется
        text

        ## Пошаговый план
        1. step

        ## Fail-fast и вопросы
        text

        ## Ожидаемый вывод
        text

        ## Примеры CLI
        - `/cmd`
        """
    ).strip() + "\n"
    return text




def test_allows_pending_research_baseline(tmp_path):
    ensure_gates_config(tmp_path, {"reviewer": {"enabled": False}})
    ticket = "demo-checkout"
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    write_active_feature(tmp_path, ticket)
    write_file(tmp_path, f"docs/prd/{ticket}.prd.md", approved_prd(ticket))
    write_plan_with_review(tmp_path, ticket)
    write_json(tmp_path, f"reports/prd/{ticket}.json", REVIEW_REPORT)
    tasklist_path = write_tasklist_ready(tmp_path, ticket)
    append_handoff(
        tasklist_path,
        "<!-- handoff:research start (source: aidd/reports/research/demo-checkout-context.json) -->\n"
        "- [ ] Research: follow-up\n"
        "<!-- handoff:research end -->\n",
    )
    baseline_doc = (
        "# Research\n\nStatus: pending\n\n## Отсутствие паттернов\n- Контекст пуст, требуется baseline\n"
    )
    write_file(tmp_path, f"docs/research/{ticket}.md", baseline_doc)
    write_json(
        tmp_path,
        f"reports/research/{ticket}-targets.json",
        {
            "ticket": ticket,
            "paths": ["src/main/kotlin"],
            "docs": [f"docs/research/{ticket}.md"],
        },
    )
    now = _timestamp()
    write_json(
        tmp_path,
        f"reports/research/{ticket}-context.json",
        {
            "ticket": ticket,
            "slug": ticket,
            "generated_at": now,
            "matches": [],
            "profile": {"is_new_project": True},
            "auto_mode": True,
        },
    )

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_progress_blocks_without_checkbox(tmp_path):
    slug = "demo-checkout"
    git_init(tmp_path)
    git_config_user(tmp_path)
    ensure_gates_config(
        tmp_path,
        {
            "prd_review": {"enabled": False},
            "researcher": {"enabled": False},
            "analyst": {"enabled": False},
            "reviewer": {"enabled": False},
        },
    )

    write_active_feature(tmp_path, slug)
    write_file(tmp_path, f"docs/prd/{slug}.prd.md", approved_prd(slug))
    write_plan_with_review(tmp_path, slug)
    write_json(tmp_path, f"reports/prd/{slug}.json", REVIEW_REPORT)
    write_research_doc(tmp_path, slug)
    write_spec_ready(tmp_path, slug)
    write_file(tmp_path, f"docs/tasklist/{slug}.md", tasklist_ready_text(slug))
    write_file(
        tmp_path,
        "src/main/kotlin/App.kt",
        "class App {\n    fun call() = \"ok\"\n}\n",
    )

    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: baseline"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    write_file(
        tmp_path,
        "src/main/kotlin/App.kt",
        "class App {\n    fun call() = \"updated\"\n}\n",
    )

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    combined = result.stdout + result.stderr
    assert "handoff-задачи" in combined or "tasks-derive" in combined

    tasklist_path = write_tasklist_ready(tmp_path, slug)
    append_handoff(
        tasklist_path,
        "- [x] Реализация :: подготовить сервис — 2024-05-01 • итерация 1\n"
        "- [ ] QA :: подготовить smoke сценарии\n"
        "<!-- handoff:research start (source: aidd/reports/research/demo-checkout-context.json) -->\n"
        "- [ ] Research: follow-up\n"
        "<!-- handoff:research end -->\n",
    )

    result_ok = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result_ok.returncode == 0, result_ok.stderr


def test_hook_uses_aidd_docs_when_workspace_has_legacy_docs(tmp_path):
    slug = "demo-checkout"
    legacy_root = tmp_path
    # legacy docs that must be ignored by hook
    write_file(legacy_root, "docs/prd/legacy.prd.md", "# Legacy PRD")
    # workspace contains aidd/ with proper docs
    project_root = ensure_project_root(legacy_root)
    write_active_feature(project_root, slug)
    write_file(project_root, f"docs/prd/{slug}.prd.md", approved_prd(slug))
    write_plan_with_review(project_root, slug)
    write_tasklist_ready(project_root, slug)
    write_research_doc(project_root, slug)
    write_json(project_root, f"reports/prd/{slug}.json", REVIEW_REPORT)
    write_file(project_root, "src/main/kotlin/App.kt", "class App")

    payload = '{"tool_input":{"file_path":"src/main/kotlin/App.kt"}}'
    result = run_hook(tmp_path, "gate-workflow.sh", payload)
    assert result.returncode == 2
    combined = (result.stdout + result.stderr).lower()
    assert "legacy" not in combined


def test_hook_requires_plugin_root(tmp_path):
    slug = "demo-checkout"
    project_root = ensure_project_root(tmp_path)
    write_active_feature(project_root, slug)
    write_file(project_root, f"docs/prd/{slug}.prd.md", approved_prd(slug))
    write_plan_with_review(project_root, slug)
    write_tasklist_ready(project_root, slug)
    write_research_doc(project_root, slug)
    write_json(project_root, f"reports/prd/{slug}.json", REVIEW_REPORT)
    write_file(project_root, "src/main/kotlin/App.kt", "class App")

    env = {"CLAUDE_PLUGIN_ROOT": ""}
    payload = '{"tool_input":{"file_path":"src/main/kotlin/App.kt"}}'
    result = run_hook(tmp_path, "gate-workflow.sh", payload, extra_env=env)
    assert result.returncode == 2
    assert "CLAUDE_PLUGIN_ROOT is required" in result.stderr


def test_hook_prefers_aidd_active_markers_over_legacy_docs(tmp_path):
    # legacy markers in workspace root must be ignored when aidd/ exists
    legacy_root = tmp_path
    write_file(legacy_root, "docs/.active_ticket", "LEGACY-1\n")
    write_file(legacy_root, "docs/.active_feature", "legacy-slug\n")

    project_root = ensure_project_root(legacy_root)
    ticket = "AIDD-123"
    write_active_feature(project_root, ticket, slug_hint="aidd-slug")
    write_file(project_root, f"docs/prd/{ticket}.prd.md", approved_prd(ticket))
    write_plan_with_review(project_root, ticket)
    write_tasklist_ready(project_root, ticket)
    write_research_doc(project_root, ticket, status="reviewed")
    write_json(
        project_root,
        f"reports/research/{ticket}-context.json",
        {"status": "reviewed", "matches": [], "targets": {"paths": ["src/main/kotlin"], "docs": []}},
    )
    write_json(
        project_root,
        f"reports/research/{ticket}-targets.json",
        {"paths": ["src/main/kotlin"], "docs": [f"docs/research/{ticket}.md"]},
    )
    write_json(project_root, f"reports/prd/{ticket}.json", REVIEW_REPORT)
    write_file(project_root, "src/main/kotlin/App.kt", "class App")

    payload = '{"tool_input":{"file_path":"src/main/kotlin/App.kt"}}'
    result = run_hook(tmp_path, "gate-workflow.sh", payload)
    assert result.returncode in (0, 2)
    combined = (result.stdout + result.stderr).lower()
    assert ticket.lower() in combined or "block" not in combined
    assert "legacy" not in combined


def test_hook_allows_with_duplicate_docs(tmp_path):
    legacy_root = tmp_path
    write_file(legacy_root, "docs/prd/legacy.prd.md", "# Legacy")
    project_root = ensure_project_root(legacy_root)
    ensure_gates_config(
        project_root,
        {
            "prd_review": {"enabled": False},
            "researcher": {"enabled": False},
            "analyst": {"enabled": False},
            "reviewer": {"enabled": False},
        },
    )
    ticket = "AIDD-456"
    write_active_feature(project_root, ticket)
    write_file(project_root, f"docs/prd/{ticket}.prd.md", approved_prd(ticket))
    write_plan_with_review(project_root, ticket)
    tasklist_path = write_tasklist_ready(project_root, ticket)
    append_handoff(
        tasklist_path,
        "- [ ] pending\n"
        "- [x] impl done\n"
        "<!-- handoff:research start (source: aidd/reports/research/AIDD-456-context.json) -->\n"
        "- [ ] Research follow-up\n"
        "<!-- handoff:research end -->\n",
    )
    write_research_doc(project_root, ticket, status="reviewed")
    write_json(project_root, f"reports/prd/{ticket}.json", REVIEW_REPORT)
    write_file(project_root, "src/main/kotlin/App.kt", "class App")
    payload = '{"tool_input":{"file_path":"src/main/kotlin/App.kt"}}'
    env = {"CLAUDE_SKIP_TASKLIST_PROGRESS": "1"}
    result = run_hook(tmp_path, "gate-workflow.sh", payload, extra_env=env)
    assert result.returncode == 0
    combined = (result.stdout + result.stderr).lower()
    assert "legacy" not in combined


def test_reviewer_marker_with_slug_hint(tmp_path):
    ticket = "FEAT-123"
    slug_hint = "checkout-lite"
    write_file(tmp_path, "src/main/kotlin/App.kt", "class App")
    ensure_gates_config(
        tmp_path,
        {
            "prd_review": {"enabled": False},
            "researcher": {"enabled": False},
            "analyst": {"enabled": False},
            "reviewer": {
                "enabled": True,
                "tests_marker": "aidd/reports/reviewer/{slug}/{scope_key}.tests.json",
                "tests_field": "tests",
                "required_values": ["required"],
                "warn_on_missing": True,
            },
        },
    )
    write_active_feature(tmp_path, ticket, slug_hint=slug_hint)
    write_file(tmp_path, f"docs/prd/{ticket}.prd.md", approved_prd(ticket))
    write_research_doc(tmp_path, ticket)
    write_plan_with_review(tmp_path, ticket)
    write_json(tmp_path, f"reports/prd/{ticket}.json", REVIEW_REPORT)
    write_tasklist_ready(tmp_path, ticket)
    reviewer_marker = {
        "ticket": ticket,
        "slug": slug_hint,
        "tests": "required",
    }
    write_json(tmp_path, f"reports/reviewer/{slug_hint}/{ticket}.tests.json", reviewer_marker)

    result = run_hook(tmp_path, "gate-workflow.sh", SRC_PAYLOAD)
    assert result.returncode == 2
    assert "reviewer запросил тесты" in result.stdout or "reviewer запросил тесты" in result.stderr
    combined_output = (result.stdout + result.stderr).lower()
    assert "checkout-lite" in combined_output
    assert "reviewer запросил тесты" in combined_output


def test_documents_are_not_blocked(tmp_path):
    write_active_feature(tmp_path, "demo-checkout")
    # PRD and plan intentionally absent

    result = run_hook(tmp_path, "gate-workflow.sh", DOC_PAYLOAD)
    assert result.returncode == 0, result.stderr

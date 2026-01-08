import json
from pathlib import Path

import pytest

from claude_workflow_cli.tools import reports_pack


def _write_context(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_research_context_pack_is_deterministic(tmp_path):
    context_path = tmp_path / "reports" / "research" / "demo-context.json"
    matches = [
        {"token": "checkout", "file": f"src/{idx}.kt", "line": idx + 1, "snippet": "x" * 300}
        for idx in range(25)
    ]
    payload = {
        "ticket": "DEMO-1",
        "slug": "demo-1",
        "generated_at": "2024-01-01T00:00:00Z",
        "keywords": ["checkout", "payments"],
        "tags": ["demo"],
        "paths": [{"path": "src", "type": "directory", "exists": True, "sample": ["src/app.kt"]}],
        "docs": [{"path": "docs/research/demo.md", "type": "file", "exists": True, "sample": []}],
        "profile": {
            "is_new_project": False,
            "src_layers": ["src/main"],
            "tests_detected": True,
            "config_detected": True,
            "logging_artifacts": ["logback.xml"],
            "recommendations": ["Use baseline"],
        },
        "manual_notes": ["note-1"],
        "reuse_candidates": [
            {"path": "src/Foo.kt", "language": "kt", "score": 3, "has_tests": True, "top_symbols": [], "imports": []}
        ],
        "matches": matches,
        "call_graph": [{"caller": "A", "callee": "B", "file": "src/app.kt", "line": 10}],
        "import_graph": ["com.demo.Foo"],
    }
    _write_context(context_path, payload)

    pack_path = reports_pack.write_research_context_pack(context_path, root=tmp_path)
    first = pack_path.read_text(encoding="utf-8")
    second = pack_path.read_text(encoding="utf-8")
    assert first == second

    packed = json.loads(first)
    assert packed["type"] == "research"
    assert packed["kind"] == "context"
    assert packed["ticket"] == "DEMO-1"
    match_rows = packed["matches"]["rows"]
    assert len(match_rows) == reports_pack.RESEARCH_LIMITS["matches"]
    assert len(match_rows[0][4]) <= reports_pack.RESEARCH_LIMITS["match_snippet_chars"]
    assert packed["profile"]["recommendations"] == ["Use baseline"]


def test_pack_format_toon_extension(tmp_path, monkeypatch):
    monkeypatch.setenv("AIDD_PACK_FORMAT", "toon")
    context_path = tmp_path / "reports" / "research" / "demo-context.json"
    payload = {"ticket": "DEMO-2", "slug": "demo-2", "generated_at": "2024-01-02T00:00:00Z"}
    _write_context(context_path, payload)

    pack_path = reports_pack.write_research_context_pack(context_path, root=tmp_path)

    assert pack_path.name.endswith(".pack.toon")
    packed = json.loads(pack_path.read_text(encoding="utf-8"))
    assert packed["ticket"] == "DEMO-2"


def test_qa_pack_includes_id_column():
    payload = {
        "ticket": "QA-1",
        "slug_hint": "qa-1",
        "generated_at": "2024-01-04T00:00:00Z",
        "findings": [
            {
                "id": "qa-issue-1",
                "severity": "major",
                "scope": "tests",
                "title": "Missing tests",
                "details": "No tests run",
                "recommendation": "Add smoke tests",
            }
        ],
    }
    pack = reports_pack.build_qa_pack(payload, source_path="reports/qa/QA-1.json")
    assert pack["findings"]["cols"][0] == "id"
    assert pack["findings"]["rows"][0][0] == "qa-issue-1"


def test_prd_pack_includes_id_column():
    payload = {
        "ticket": "PRD-1",
        "slug": "prd-1",
        "generated_at": "2024-01-05T00:00:00Z",
        "findings": [
            {
                "id": "prd-issue-1",
                "severity": "major",
                "title": "Placeholder",
                "details": "TBD present in PRD",
            }
        ],
    }
    pack = reports_pack.build_prd_pack(payload, source_path="reports/prd/PRD-1.json")
    assert pack["findings"]["cols"][0] == "id"
    assert pack["findings"]["rows"][0][0] == "prd-issue-1"


def test_research_pack_budget_helper(tmp_path):
    context_path = tmp_path / "reports" / "research" / "tiny-context.json"
    payload = {"ticket": "DEMO-3", "slug": "demo-3", "generated_at": "2024-01-03T00:00:00Z"}
    _write_context(context_path, payload)

    pack_path = reports_pack.write_research_context_pack(context_path, root=tmp_path)
    pack_text = pack_path.read_text(encoding="utf-8")

    errors = reports_pack.check_budget(
        pack_text,
        max_chars=reports_pack.RESEARCH_BUDGET["max_chars"],
        max_lines=reports_pack.RESEARCH_BUDGET["max_lines"],
        label="research",
    )
    assert not errors


def test_budget_helper_explains_how_to_fix():
    text = "x" * 50
    errors = reports_pack.check_budget(text, max_chars=10, max_lines=1, label="demo")
    assert errors
    assert "Reduce top-N" in errors[0]


def test_budget_enforcement_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("AIDD_PACK_ENFORCE_BUDGET", "1")
    context_path = tmp_path / "reports" / "research" / "huge-context.json"
    payload = {
        "ticket": "X" * 2000,
        "slug": "huge",
        "generated_at": "2024-01-06T00:00:00Z",
    }
    _write_context(context_path, payload)

    with pytest.raises(ValueError) as exc:
        reports_pack.write_research_context_pack(context_path, root=tmp_path)
    assert "pack budget exceeded" in str(exc.value)

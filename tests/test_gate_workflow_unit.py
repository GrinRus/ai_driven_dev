from __future__ import annotations

from pathlib import Path

from aidd_runtime import gate_workflow


def _write_tasklist(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "tasklist.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_select_file_path_prefers_src() -> None:
    paths = ["docs/readme.md", "src/main/kotlin/App.kt", "lib/util.py"]
    assert gate_workflow._select_file_path(paths) == "src/main/kotlin/App.kt"


def test_next3_has_real_items_accepts_real_entry(tmp_path: Path) -> None:
    path = _write_tasklist(
        tmp_path,
        "## AIDD:NEXT_3\n- [ ] TASK-1: do it\n",
    )
    assert gate_workflow._next3_has_real_items(path) is True


def test_next3_has_real_items_rejects_placeholders(tmp_path: Path) -> None:
    path = _write_tasklist(
        tmp_path,
        "## AIDD:NEXT_3\n- [ ] <1. task>\n",
    )
    assert gate_workflow._next3_has_real_items(path) is False

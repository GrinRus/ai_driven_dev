import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:  # pragma: no cover - environment setup
    sys.path.insert(0, str(TOOLS_DIR))

from check_payload_sync import DEFAULT_PATHS, compare_paths, parse_paths  # type: ignore  # noqa: E402

PAYLOAD_ROOT = REPO_ROOT / "src" / "claude_workflow_cli" / "data" / "payload"


def _prepare_tree(base: Path, relative: str, files: dict[str, str]) -> None:
    target = base / relative
    for rel_path, content in files.items():
        file_path = target / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")


def test_compare_paths_ok(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    payload = tmp_path / "payload"
    _prepare_tree(repo, "docs", {"readme.md": "hello"})
    _prepare_tree(payload, "docs", {"readme.md": "hello"})

    mismatches = compare_paths(repo, payload, ["docs"])

    assert mismatches == []


def test_compare_paths_detects_hash_difference(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    payload = tmp_path / "payload"
    _prepare_tree(repo, "docs", {"readme.md": "hello"})
    _prepare_tree(payload, "docs", {"readme.md": "bye"})

    mismatches = compare_paths(repo, payload, ["docs"])

    assert "docs/readme.md: hash mismatch" in mismatches


def test_compare_paths_detects_missing_side(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    payload = tmp_path / "payload"
    _prepare_tree(repo, "docs", {"readme.md": "hello"})
    _prepare_tree(payload, "docs", {"readme.md": "hello", "extra.md": "??"})

    mismatches = compare_paths(repo, payload, ["docs"])

    assert "docs/extra.md: exists only in payload snapshot" in mismatches


def test_parse_paths_splits_commas() -> None:
    paths = parse_paths(["docs,templates", "scripts"])
    assert paths == ["docs", "templates", "scripts"]


def test_repo_and_payload_default_paths_in_sync() -> None:
    mismatches = compare_paths(REPO_ROOT, PAYLOAD_ROOT, DEFAULT_PATHS)
    assert mismatches == []

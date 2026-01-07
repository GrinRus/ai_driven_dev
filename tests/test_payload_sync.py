import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:  # pragma: no cover - environment setup
    sys.path.insert(0, str(TOOLS_DIR))

from check_payload_sync import (  # type: ignore  # noqa: E402
    DEFAULT_PATHS,
    DEFAULT_PAYLOAD_PREFIX,
    compare_paths,
    parse_paths,
    resolve_snapshot_root,
)

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

    mismatches = compare_paths(repo, payload, repo, ["docs"], payload_prefix="")

    assert mismatches == []


def test_compare_paths_detects_hash_difference(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    payload = tmp_path / "payload"
    _prepare_tree(repo, "docs", {"readme.md": "hello"})
    _prepare_tree(payload, "docs", {"readme.md": "bye"})

    mismatches = compare_paths(repo, payload, repo, ["docs"], payload_prefix="")

    assert "docs/readme.md: hash mismatch" in mismatches


def test_compare_paths_detects_missing_side(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    payload = tmp_path / "payload"
    _prepare_tree(repo, "docs", {"readme.md": "hello"})
    _prepare_tree(payload, "docs", {"readme.md": "hello", "extra.md": "??"})

    mismatches = compare_paths(repo, payload, repo, ["docs"], payload_prefix="")

    assert "docs/extra.md: exists only in payload snapshot" in mismatches


def test_parse_paths_splits_commas() -> None:
    paths = parse_paths(["docs,templates", "hooks"])
    assert paths == ["docs", "templates", "hooks"]


def test_repo_and_payload_default_paths_in_sync() -> None:
    snapshot_root = resolve_snapshot_root(REPO_ROOT, DEFAULT_PAYLOAD_PREFIX)
    if snapshot_root == REPO_ROOT and DEFAULT_PAYLOAD_PREFIX:
        return
    mismatches = compare_paths(
        REPO_ROOT,
        PAYLOAD_ROOT,
        snapshot_root,
        DEFAULT_PATHS,
        payload_prefix=DEFAULT_PAYLOAD_PREFIX,
    )
    assert mismatches == []

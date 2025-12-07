import sys
from pathlib import Path


def _find_repo_root(marker: str = "pyproject.toml") -> Path:
    path = Path(__file__).resolve()
    for parent in path.parents:
        if (parent / marker).exists():
            return parent
    # Fallback to the first parent that should be the repository root layout
    return Path(__file__).resolve().parents[6]


REPO_ROOT = _find_repo_root()
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:  # pragma: no cover - environment setup
    sys.path.insert(0, str(TOOLS_DIR))

from check_payload_sync import DEFAULT_PATHS, compare_paths, parse_paths  # type: ignore  # noqa: E402

PAYLOAD_ROOT = REPO_ROOT / "src" / "claude_workflow_cli" / "data" / "payload" / "aidd"


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

    mismatches = compare_paths(repo, payload, ["docs"], payload_prefix="")

    assert mismatches == []


def test_compare_paths_detects_hash_difference(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    payload = tmp_path / "payload"
    _prepare_tree(repo, "docs", {"readme.md": "hello"})
    _prepare_tree(payload, "docs", {"readme.md": "bye"})

    mismatches = compare_paths(repo, payload, ["docs"], payload_prefix="")

    assert "docs/readme.md: hash mismatch" in mismatches


def test_compare_paths_detects_missing_side(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    payload = tmp_path / "payload"
    _prepare_tree(repo, "docs", {"readme.md": "hello"})
    _prepare_tree(payload, "docs", {"readme.md": "hello", "extra.md": "??"})

    mismatches = compare_paths(repo, payload, ["docs"], payload_prefix="")

    assert "docs/extra.md: exists only in payload snapshot" in mismatches


def test_parse_paths_splits_commas() -> None:
    paths = parse_paths(["docs,templates", "scripts"])
    assert paths == ["docs", "templates", "scripts"]


def test_repo_and_payload_default_paths_in_sync() -> None:
    mismatches = compare_paths(REPO_ROOT, PAYLOAD_ROOT, DEFAULT_PATHS, payload_prefix="")
    assert mismatches == []


def test_default_paths_cover_agent_first_artifacts() -> None:
    required = {"README.md", "README.en.md", "CHANGELOG.md"}
    for path in required:
        assert path in DEFAULT_PATHS


def test_default_paths_do_not_include_dev_only_content() -> None:
    assert "doc" not in DEFAULT_PATHS

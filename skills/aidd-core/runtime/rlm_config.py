from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable

from aidd_runtime.resources import DEFAULT_PROJECT_SUBDIR, resolve_project_root as resolve_workspace_root


DEFAULT_PROMPT_VERSION = "v1"
DEFAULT_IGNORE_DIRS = {
    ".git",
    ".gradle",
    ".idea",
    ".venv",
    "aidd",
    "build",
    "dist",
    "node_modules",
    "out",
    "output",
    "target",
    "vendor",
}
LANG_BY_EXT = {
    ".kt": "kt",
    ".kts": "kts",
    ".java": "java",
    ".py": "py",
    ".js": "js",
    ".jsx": "js",
    ".ts": "ts",
    ".tsx": "ts",
    ".go": "go",
    ".rs": "rs",
    ".rb": "rb",
    ".cs": "cs",
    ".php": "php",
    ".swift": "swift",
    ".scala": "scala",
    ".sql": "sql",
    ".sh": "sh",
    ".bash": "sh",
    ".zsh": "sh",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".xml": "xml",
    ".properties": "properties",
    ".gradle": "gradle",
}
SPECIAL_FILES = {
    "Makefile": "make",
    "Dockerfile": "docker",
}


def load_conventions(root: Path) -> Dict:
    path = root / "config" / "conventions.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_rlm_settings(root: Path) -> Dict:
    cfg = load_conventions(root)
    rlm = cfg.get("rlm")
    if isinstance(rlm, dict):
        return rlm
    researcher = cfg.get("researcher") if isinstance(cfg.get("researcher"), dict) else {}
    rlm = researcher.get("rlm")
    return rlm if isinstance(rlm, dict) else {}


def workspace_root_for(root: Path) -> Path:
    workspace_root, _ = resolve_workspace_root(root, DEFAULT_PROJECT_SUBDIR)
    return workspace_root


def paths_base_for(root: Path) -> Path:
    workspace_root = workspace_root_for(root)
    base = workspace_root if root.name == "aidd" else root
    cfg = load_conventions(root)
    researcher = cfg.get("researcher") if isinstance(cfg.get("researcher"), dict) else {}
    defaults = researcher.get("defaults") if isinstance(researcher, dict) else {}
    if isinstance(defaults, dict):
        flag = defaults.get("workspace_relative")
        if flag is False:
            return root
        if flag is True:
            return workspace_root
    return base


def base_label(root: Path, base_root: Path) -> str:
    workspace_root = workspace_root_for(root)
    if base_root.resolve() == workspace_root.resolve():
        return "workspace"
    return "aidd"


def base_root_for_label(root: Path, label: str | None) -> Path:
    workspace_root = workspace_root_for(root)
    if str(label).strip().lower() == "aidd":
        return root
    if str(label).strip().lower() == "workspace":
        return workspace_root
    return paths_base_for(root)


def resolve_source_path(
    path: Path,
    *,
    project_root: Path,
    workspace_root: Path,
    preferred_root: Path | None = None,
) -> Path:
    if path.is_absolute():
        return path.resolve()
    roots = [root for root in (preferred_root, workspace_root, project_root) if root is not None]
    seen = set()
    ordered: list[Path] = []
    for root in roots:
        key = root.resolve()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(root)
    fallback = ordered[0] if ordered else project_root
    for root in ordered:
        candidate = (root / path).resolve()
        if candidate.exists():
            return candidate
    return (fallback / path).resolve()


def normalize_path(path: Path) -> str:
    raw = path.as_posix().lstrip("./")
    return raw


def file_id_for_path(path: Path) -> str:
    normalized = normalize_path(path)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def rev_sha_for_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def detect_lang(path: Path) -> str:
    if path.name in SPECIAL_FILES:
        return SPECIAL_FILES[path.name]
    ext = path.suffix.lower()
    return LANG_BY_EXT.get(ext, "")


def normalize_ignore_dirs(raw: Iterable[str] | None) -> set[str]:
    if not raw:
        return set(DEFAULT_IGNORE_DIRS)
    items = {str(item).strip().lower() for item in raw if str(item).strip()}
    return items or set(DEFAULT_IGNORE_DIRS)


def prompt_version(settings: Dict) -> str:
    raw = settings.get("prompt_version")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return DEFAULT_PROMPT_VERSION

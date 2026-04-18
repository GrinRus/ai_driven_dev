from __future__ import annotations

import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

_ENV_KEYS = ("CLAUDE_PLUGIN_ROOT", "AIDD_PLUGIN_DIR")


def _looks_like_plugin_root(candidate: Path) -> bool:
    return (candidate / ".claude-plugin").exists() and (candidate / "skills").is_dir()


def _looks_like_import_root(candidate: Path) -> bool:
    return _looks_like_plugin_root(candidate) and (candidate / "aidd_runtime").is_dir()


def _resolve_env_plugin_root() -> Path | None:
    for key in _ENV_KEYS:
        env_root = str(os.environ.get(key, "")).strip()
        if not env_root:
            continue
        candidate = Path(env_root).expanduser().resolve()
        if _looks_like_plugin_root(candidate):
            return candidate
    return None


def resolve_repo_root(start_file: str | Path | None = None) -> Path:
    env_plugin_root = _resolve_env_plugin_root()
    if env_plugin_root is not None and _looks_like_import_root(env_plugin_root):
        return env_plugin_root

    for key in _ENV_KEYS:
        env_root = str(os.environ.get(key, "")).strip()
        if not env_root:
            continue
        candidate = Path(env_root).expanduser().resolve()
        if _looks_like_import_root(candidate):
            return candidate

    probe = Path(start_file or __file__).expanduser().resolve()
    for parent in (probe.parent, *probe.parents):
        if _looks_like_import_root(parent):
            return parent
    raise RuntimeError("unable to resolve AIDD repository root for runtime bootstrap")


def ensure_repo_root(start_file: str | Path | None = None) -> Path:
    repo_root = resolve_repo_root(start_file)
    env_plugin_root = _resolve_env_plugin_root()
    normalized_plugin_root = str((env_plugin_root or repo_root).resolve())
    os.environ["CLAUDE_PLUGIN_ROOT"] = normalized_plugin_root
    if str(os.environ.get("AIDD_PLUGIN_DIR", "")).strip():
        os.environ["AIDD_PLUGIN_DIR"] = normalized_plugin_root
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return repo_root


def export_module(module_name: str, namespace: dict[str, Any]) -> ModuleType:
    ensure_repo_root(__file__)
    from aidd_runtime.entrypoint import export_module as _export_module

    return _export_module(module_name, namespace)


def run_main(module_name: str, argv: list[str] | None = None) -> int:
    ensure_repo_root(__file__)
    from aidd_runtime.entrypoint import run_main as _run_main

    return _run_main(module_name, argv)


__all__ = [
    "ensure_repo_root",
    "export_module",
    "resolve_repo_root",
    "run_main",
]

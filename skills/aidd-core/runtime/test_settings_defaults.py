from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

BASE_COMMON_PATTERNS = ("config/",)

COMMON_PATTERNS_BY_TOOL: dict[str, tuple[str, ...]] = {
    "gradle": (
        "**/build.gradle",
        "**/build.gradle.kts",
        "**/settings.gradle",
        "**/settings.gradle.kts",
        "**/gradle/libs.versions.toml",
        "**/buildSrc/**",
    ),
    "npm": (
        "**/package.json",
        "**/package-lock.json",
        "**/pnpm-lock.yaml",
        "**/yarn.lock",
        "**/npm-shrinkwrap.json",
    ),
    "python": (
        "**/pyproject.toml",
        "**/requirements*.txt",
        "**/Pipfile",
        "**/Pipfile.lock",
        "**/poetry.lock",
        "**/setup.py",
        "**/setup.cfg",
    ),
    "go": (
        "**/go.mod",
        "**/go.sum",
    ),
    "rust": (
        "**/Cargo.toml",
        "**/Cargo.lock",
    ),
    "dotnet": (
        "**/*.csproj",
        "**/*.fsproj",
        "**/*.vbproj",
        "**/Directory.Packages.props",
        "**/packages.config",
        "**/packages.lock.json",
        "**/global.json",
        "**/nuget.config",
    ),
}

DEFAULT_COMMON_PATTERNS = tuple(
    pattern for pattern in BASE_COMMON_PATTERNS + sum(COMMON_PATTERNS_BY_TOOL.values(), ())
)

DEFAULT_CODE_PATHS = (
    "src",
    "app",
    "apps",
    "modules",
    "packages",
    "service",
    "services",
    "backend",
    "frontend",
    "lib",
    "libs",
    "server",
    "client",
    "core",
    "domain",
    "shared",
    "python",
    "java",
    "kotlin",
    "cmd",
    "pkg",
    "internal",
    "crates",
)

DEFAULT_CODE_EXTENSIONS = (
    ".kt",
    ".kts",
    ".java",
    ".groovy",
    ".gradle",
    ".gradle.kts",
    ".scala",
    ".swift",
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hpp",
    ".cs",
    ".csproj",
    ".fs",
    ".fsx",
    ".fsproj",
    ".fsharp",
    ".vb",
    ".vbproj",
    ".go",
    ".rb",
    ".rs",
    ".py",
    ".pyi",
    ".pyx",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".m",
    ".mm",
    ".php",
    ".dart",
    ".mjs",
    ".cjs",
    ".hs",
    ".erl",
    ".ex",
    ".exs",
    ".cls",
)

DEFAULT_CODE_FILES = (
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "gradle/libs.versions.toml",
    "pom.xml",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "npm-shrinkwrap.json",
    "pyproject.toml",
    "requirements.txt",
    "pipfile",
    "pipfile.lock",
    "poetry.lock",
    "setup.py",
    "setup.cfg",
    "go.mod",
    "go.sum",
    "cargo.toml",
    "cargo.lock",
    "directory.packages.props",
    "packages.config",
    "packages.lock.json",
    "global.json",
    "nuget.config",
)

_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".claude",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "__pycache__",
    ".tox",
    ".mypy_cache",
    "aidd",
}


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def detect_build_tools(root: Path) -> set[str]:
    detected: set[str] = set()
    if not root.exists():
        return detected

    gradle_names = {
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "settings.gradle.kts",
    }
    npm_names = {
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "npm-shrinkwrap.json",
    }
    python_names = {
        "pyproject.toml",
        "pipfile",
        "pipfile.lock",
        "poetry.lock",
        "setup.py",
        "setup.cfg",
    }
    go_names = {"go.mod", "go.sum"}
    rust_names = {"cargo.toml", "cargo.lock"}
    dotnet_names = {
        "directory.packages.props",
        "packages.config",
        "packages.lock.json",
        "global.json",
        "nuget.config",
    }

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        parts = {part.lower() for part in Path(dirpath).parts}
        for name in filenames:
            lower = name.lower()
            if lower in gradle_names:
                detected.add("gradle")
            if lower == "libs.versions.toml" and "gradle" in parts:
                detected.add("gradle")
            if lower in npm_names:
                detected.add("npm")
            if lower in python_names or (lower.startswith("requirements") and lower.endswith(".txt")):
                detected.add("python")
            if lower in go_names:
                detected.add("go")
            if lower in rust_names:
                detected.add("rust")
            if lower.endswith((".csproj", ".fsproj", ".vbproj")) or lower in dotnet_names:
                detected.add("dotnet")
    return detected


def test_settings_payload(detected: set[str] | None = None) -> dict[str, list[str]]:
    if detected:
        patterns: list[str] = list(BASE_COMMON_PATTERNS)
        for tool in sorted(detected):
            patterns.extend(COMMON_PATTERNS_BY_TOOL.get(tool, ()))
        common_patterns = _dedupe(patterns)
    else:
        common_patterns = list(DEFAULT_COMMON_PATTERNS)

    return {
        "commonPatterns": common_patterns,
        "codePaths": list(DEFAULT_CODE_PATHS),
        "codeExtensions": list(DEFAULT_CODE_EXTENSIONS),
        "codeFiles": list(DEFAULT_CODE_FILES),
    }

#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path


HOOK_PREFIX = "[lint-deps]"

GRADLE_DEPS_FILES = (
    "**/build.gradle",
    "**/build.gradle.kts",
    "**/settings.gradle",
    "**/settings.gradle.kts",
    "**/gradle/libs.versions.toml",
)

DEFAULT_DEPS_FILES = (
    *GRADLE_DEPS_FILES,
    "**/package.json",
    "**/pyproject.toml",
    "**/requirements*.txt",
    "**/Pipfile",
    "**/setup.py",
    "**/setup.cfg",
    "**/go.mod",
    "**/Cargo.toml",
    "**/*.csproj",
    "**/*.fsproj",
    "**/*.vbproj",
    "**/Directory.Packages.props",
    "**/packages.config",
    "**/global.json",
    "**/nuget.config",
)

PACKAGE_JSON_IGNORE = {
    "name",
    "version",
    "private",
    "description",
    "license",
    "author",
    "repository",
    "homepage",
    "scripts",
    "workspaces",
    "engines",
    "files",
    "exports",
    "main",
    "module",
    "types",
}

TOML_IGNORE_KEYS = {
    "name",
    "version",
    "description",
    "authors",
    "license",
    "edition",
    "dependencies",
    "dev-dependencies",
    "optional-dependencies",
    "python",
    "python_version",
    "python_full_version",
    "readme",
    "homepage",
    "repository",
    "documentation",
    "keywords",
}

TOML_DEP_LIST_KEYS = {
    "dependencies",
    "dev-dependencies",
    "optional-dependencies",
}

SETUP_PY_KEYS = {
    "install_requires",
    "tests_require",
    "setup_requires",
    "extras_require",
}

PIPFILE_LOCK_IGNORE = {
    "_meta",
    "default",
    "develop",
}


def _bootstrap() -> Path:
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not raw:
        print(f"{HOOK_PREFIX} CLAUDE_PLUGIN_ROOT is required to run hooks.", file=sys.stderr)
        raise SystemExit(2)
    plugin_root = Path(raw).expanduser().resolve()
    if str(plugin_root) not in sys.path:
        sys.path.insert(0, str(plugin_root))
    vendor_dir = Path(__file__).resolve().parent / "_vendor"
    if vendor_dir.exists():
        sys.path.insert(0, str(vendor_dir))
    return plugin_root


def _log_stdout(message: str) -> None:
    from hooks import hooklib

    if message:
        print(hooklib.prefix_lines(HOOK_PREFIX, message))


def _run_git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        text=True,
        capture_output=True,
    )


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_dep_files(config_path: Path) -> list[str]:
    data = _load_json(config_path)
    raw_files = data.get("deps_allowlist_files") or data.get("depsAllowlistFiles")
    if isinstance(raw_files, list):
        items = [str(item).strip() for item in raw_files if str(item).strip()]
        if items:
            return items
    elif isinstance(raw_files, str) and raw_files.strip():
        return [raw_files.strip()]

    mode = str(data.get("deps_allowlist_mode") or data.get("depsAllowlistMode") or "").strip().lower()
    if mode in {"gradle-only", "gradle_only", "gradle"}:
        return list(GRADLE_DEPS_FILES)
    return list(DEFAULT_DEPS_FILES)


def _parse_diff_added_lines(diff_text: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    current_path: str | None = None
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current_path = None
            continue
        if line.startswith("+++ b/"):
            path = line[6:].strip()
            if path == "/dev/null":
                current_path = None
            else:
                current_path = path
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        if not current_path:
            continue
        result.setdefault(current_path, []).append(line[1:])
    return result


def _extract_gradle(lines: list[str]) -> set[str]:
    deps: set[str] = set()
    coord_re = re.compile(
        r"(implementation|api|compileOnly|runtimeOnly|testImplementation|testRuntimeOnly|testCompileOnly)"
        r"\\s*\\(?\\s*[\"']([^:\"'\\)]+:[^:\"'\\)]+)"
    )
    module_re = re.compile(r"module\\s*=\\s*[\"']([^:\"'\\)]+:[^:\"'\\)]+)")
    inline_re = re.compile(r"=\\s*[\"']([^:\"'\\)]+:[^:\"'\\)]+):[^\"']+[\"']")
    for line in lines:
        match = coord_re.search(line)
        if match:
            deps.add(match.group(2))
            continue
        match = module_re.search(line)
        if match:
            deps.add(match.group(1))
            continue
        match = inline_re.search(line)
        if match:
            deps.add(match.group(1))
    return deps


def _extract_package_json(lines: list[str]) -> set[str]:
    deps: set[str] = set()
    dep_re = re.compile(r"\"(@?[^\"\\s]+)\"\\s*:\\s*\"[^\"]+\"")
    for line in lines:
        match = dep_re.search(line)
        if not match:
            continue
        name = match.group(1).strip()
        if name in PACKAGE_JSON_IGNORE:
            continue
        deps.add(name)
    return deps


def _clean_requirement(raw: str) -> str:
    value = raw.strip().strip('"').strip("'")
    value = value.rstrip(",")
    value = value.split(";", 1)[0].strip()
    if not value:
        return ""
    if value.startswith("-"):
        return ""
    if value.startswith("--"):
        return ""
    value = value.split("@", 1)[0].strip()
    value = value.split("[", 1)[0].strip()
    for splitter in ("==", ">=", "<=", "~=", "!=", ">", "<"):
        if splitter in value:
            value = value.split(splitter, 1)[0].strip()
            break
    if " " in value:
        value = value.split(" ", 1)[0].strip()
    return value


def _extract_requirements(lines: list[str]) -> set[str]:
    deps: set[str] = set()
    for line in lines:
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        name = _clean_requirement(clean)
        if name:
            deps.add(name)
    return deps


def _extract_toml_dependencies(lines: list[str]) -> set[str]:
    deps: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "[")):
            continue
        if "=" in stripped:
            key, value = stripped.split("=", 1)
            key = key.strip().strip('"').strip("'")
            if not key:
                continue
            key_lower = key.lower()
            if key_lower in TOML_DEP_LIST_KEYS:
                for match in re.findall(r"[\"']([^\"']+)[\"']", value):
                    name = _clean_requirement(match)
                    if name:
                        deps.add(name)
                continue
            if key_lower in TOML_IGNORE_KEYS:
                continue
            deps.add(key)
            continue
        if stripped.startswith(("\"", "'")):
            name = _clean_requirement(stripped)
            if name:
                deps.add(name)
    return deps


def _extract_setup_cfg(lines: list[str]) -> set[str]:
    deps: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("["):
            continue
        if "=" in stripped:
            continue
        name = _clean_requirement(stripped)
        if name:
            deps.add(name)
    return deps


def _extract_string_literals(line: str) -> list[str]:
    results: list[str] = []
    for match in re.finditer(r"([\"'])(.+?)\\1", line):
        value = match.group(2)
        tail = line[match.end():].lstrip()
        if tail.startswith(":"):
            continue
        cleaned = _clean_requirement(value)
        if cleaned:
            results.append(cleaned)
    return results


def _extract_setup_py(lines: list[str]) -> set[str]:
    deps: set[str] = set()
    active_key: str | None = None
    bracket_depth = 0
    key_re = re.compile(r"\\b(" + "|".join(SETUP_PY_KEYS) + r")\\b\\s*=")
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if active_key:
            deps.update(_extract_string_literals(stripped))
            bracket_depth += stripped.count("[") + stripped.count("{") + stripped.count("(")
            bracket_depth -= stripped.count("]") + stripped.count("}") + stripped.count(")")
            if bracket_depth <= 0:
                active_key = None
                bracket_depth = 0
            continue
        match = key_re.search(stripped)
        if not match:
            continue
        remainder = stripped[match.end():]
        deps.update(_extract_string_literals(remainder))
        bracket_depth = remainder.count("[") + remainder.count("{") + remainder.count("(")
        bracket_depth -= remainder.count("]") + remainder.count("}") + remainder.count(")")
        if bracket_depth > 0:
            active_key = match.group(1)
    return deps


def _extract_pipfile(lines: list[str]) -> set[str]:
    deps: set[str] = set()
    section: str | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped.strip("[]").strip()
            continue
        if section not in {"packages", "dev-packages"}:
            continue
        if "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip().strip('"').strip("'")
        if not key or key.lower() in TOML_IGNORE_KEYS:
            continue
        deps.add(key)
    return deps


def _extract_pipfile_lock(lines: list[str]) -> set[str]:
    deps: set[str] = set()
    section: str | None = None
    section_re = re.compile(r"\"(default|develop)\"\\s*:\\s*{")
    dep_re = re.compile(r"\"([^\"]+)\"\\s*:\\s*{")
    for line in lines:
        stripped = line.strip()
        match = section_re.match(stripped)
        if match:
            section = match.group(1)
            continue
        match = dep_re.match(stripped)
        if not match or not section:
            continue
        name = match.group(1)
        if name in PIPFILE_LOCK_IGNORE:
            continue
        deps.add(name)
    return deps


def _extract_poetry_lock(lines: list[str]) -> set[str]:
    deps: set[str] = set()
    in_package = False
    name_re = re.compile(r"name\\s*=\\s*[\"']([^\"']+)[\"']")
    for line in lines:
        stripped = line.strip()
        if stripped == "[[package]]":
            in_package = True
            continue
        if not in_package:
            continue
        match = name_re.match(stripped)
        if match:
            deps.add(match.group(1))
            in_package = False
    return deps


def _extract_go(lines: list[str]) -> set[str]:
    deps: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "module ", "go ", "replace ", "exclude ")):
            continue
        if stripped == "require (" or stripped == ")":
            continue
        if stripped.startswith("require "):
            stripped = stripped[len("require ") :].strip()
        parts = stripped.split()
        if parts:
            deps.add(parts[0])
    return deps


def _extract_rust(lines: list[str]) -> set[str]:
    deps: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "[")):
            continue
        if "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip().strip('"').strip("'")
        if not key or key.lower() in TOML_IGNORE_KEYS:
            continue
        deps.add(key)
    return deps


def _extract_dotnet(lines: list[str]) -> set[str]:
    deps: set[str] = set()
    include_re = re.compile(r"Package(?:Reference|Version)\\s+[^>]*\\b(?:Include|Update)=\"([^\"]+)\"")
    pkg_re = re.compile(r"\\bPackageReference\\b[^>]*\\bInclude=\"([^\"]+)\"")
    config_re = re.compile(r"\\bid=\"([^\"]+)\"")
    for line in lines:
        match = include_re.search(line)
        if match:
            deps.add(match.group(1))
            continue
        match = pkg_re.search(line)
        if match:
            deps.add(match.group(1))
            continue
        match = config_re.search(line)
        if match:
            deps.add(match.group(1))
    return deps


def _extract_dependencies(path: str, lines: list[str]) -> set[str]:
    lower = path.lower()
    name = Path(lower).name
    if lower.endswith((".gradle", ".gradle.kts")) or name == "libs.versions.toml":
        return _extract_gradle(lines)
    if name == "package.json":
        return _extract_package_json(lines)
    if name == "setup.py":
        return _extract_setup_py(lines)
    if name == "pipfile":
        return _extract_pipfile(lines)
    if name in {"pyproject.toml", "pipfile.lock", "poetry.lock", "setup.cfg"}:
        if name == "pipfile.lock":
            return _extract_pipfile_lock(lines)
        if name == "poetry.lock":
            return _extract_poetry_lock(lines)
        if name == "setup.cfg":
            return _extract_setup_cfg(lines)
        return _extract_toml_dependencies(lines)
    if name.startswith("requirements") and name.endswith(".txt"):
        return _extract_requirements(lines)
    if name in {"go.mod", "go.sum"}:
        return _extract_go(lines)
    if name == "cargo.toml":
        return _extract_rust(lines)
    if lower.endswith((".csproj", ".fsproj", ".vbproj")) or name in {
        "directory.packages.props",
        "packages.config",
    }:
        return _extract_dotnet(lines)
    return set()


def main() -> int:
    _bootstrap()
    from hooks import hooklib

    ctx = hooklib.read_hook_context()
    root, _ = hooklib.resolve_project_root(ctx)
    if not (root / "docs").is_dir():
        return 0
    if hooklib.resolve_hooks_mode() == "fast":
        return 0

    config_path = root / "config" / "gates.json"
    if not hooklib.config_get_bool(config_path, "deps_allowlist", False):
        return 0

    dep_files = _resolve_dep_files(config_path)
    if dep_files:
        changed_files = hooklib.collect_changed_files(root)
        if not any(fnmatch(path, pattern) for path in changed_files for pattern in dep_files):
            return 0

    allow_path = root / "config" / "allowed-deps.txt"
    if not allow_path.is_file():
        return 0

    allowed: set[str] = set()
    for raw in allow_path.read_text(encoding="utf-8").splitlines():
        stripped = raw.split("#", 1)[0].strip()
        stripped = "".join(stripped.split())
        if stripped:
            allowed.add(stripped)

    if not allowed:
        return 0

    added_lines: dict[str, list[str]] = {}
    if hooklib.git_has_head(root):
        result = _run_git(
            root,
            [
                "diff",
                "--unified=0",
                "--no-color",
                "HEAD",
                "--",
                *dep_files,
            ],
        )
        if result.returncode == 0:
            added_lines = _parse_diff_added_lines(result.stdout)

    allowed_lower = {item.lower() for item in allowed}
    for path, lines in added_lines.items():
        deps = _extract_dependencies(path, lines)
        for dep in sorted(deps):
            if dep in allowed or dep.lower() in allowed_lower:
                continue
            _log_stdout(f"WARN: dependency '{dep}' не в allowlist (config/allowed-deps.txt)")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

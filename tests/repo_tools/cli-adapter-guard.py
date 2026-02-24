#!/usr/bin/env python3
"""Validate strict CLI adapter contract for skill runtime entrypoints."""

from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_GLOB = "skills/**/runtime/**/*.py"
MAIN_GUARD_RE = re.compile(r"""if __name__\s*==\s*['"]__main__['"]""")
USAGE_RE = re.compile(r"\busage:", flags=re.IGNORECASE)
EXAMPLES_RE = re.compile(r"(?im)^\s*(examples?|пример(?:ы)?)\s*:")
OUTPUTS_RE = re.compile(r"(?im)^\s*(outputs?|artifacts?|результат(?:ы)?)\s*:")
EXIT_CODES_RE = re.compile(r"(?im)^\s*(exit\s*codes?|return\s*codes?|коды?\s+выхода)\s*:")
OPTIONS_HEADING_RE = re.compile(r"(?im)^\s*(options?|optional arguments|positional arguments)\s*:")
OPTION_LINE_RE = re.compile(r"(?m)^\s*(?:-\w\b|--[A-Za-z0-9][A-Za-z0-9_-]*)")
DESCRIPTION_PLACEHOLDER_RE = re.compile(r"\b(tbd|todo|n/a|coming soon)\b", flags=re.IGNORECASE)
ARGPARSE_RE = re.compile(r"\bargparse\b|\badd_argument\s*\(")
COMBINED_SECTION_RE = re.compile(
    r"(?im)^\s*(?:examples?|пример(?:ы)?|outputs?|artifacts?|результат(?:ы)?|"
    r"exit\s*codes?|return\s*codes?|коды?\s+выхода|options?|optional arguments|positional arguments)\s*:"
)
HELP_OPTION_RE = re.compile(r"(?<!\S)(-\w|--[A-Za-z0-9][A-Za-z0-9_-]*)")

HOOK_SIGNAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("import_hooklib", re.compile(r"""from\s+hooks\s+import\s+hooklib""")),
    ("import_hooks_dot_hooklib", re.compile(r"""import\s+hooks\.hooklib""")),
    ("read_hook_context", re.compile(r"""read_hook_context\s*\(""")),
    ("hook_bootstrap_message", re.compile(r"""required to run hooks\.""")),
)


@dataclass(frozen=True)
class CheckResult:
    errors: list[str]
    warnings: list[str]
    total_runtime: int
    cli_entrypoints: int
    library_runtime: int


def _iter_runtime_paths(repo_root: Path) -> list[Path]:
    paths = sorted(path for path in repo_root.glob(RUNTIME_GLOB) if path.name != "__init__.py")
    return [path for path in paths if path.is_file()]


def _is_cli_entrypoint(text: str) -> bool:
    if MAIN_GUARD_RE.search(text):
        return True
    return "exec(compile(" in text and "_CORE_PATH" in text


def _hook_signals(text: str) -> list[str]:
    return [name for name, pattern in HOOK_SIGNAL_PATTERNS if pattern.search(text)]


def _run_help(repo_root: Path, script_path: Path) -> tuple[int, str, bool]:
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(repo_root)
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(repo_root) if not existing_pythonpath else f"{repo_root}:{existing_pythonpath}"
    try:
        proc = subprocess.run(
            ["python3", str(script_path), "--help"],
            cwd=repo_root,
            env=env,
            text=True,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=20,
        )
    except subprocess.TimeoutExpired as exc:
        output = ((exc.stdout or "") + "\n" + (exc.stderr or "")).strip()
        return (124, output, True)
    combined = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    return (proc.returncode, combined, False)


def _extract_section_window(output: str, section_re: re.Pattern[str]) -> str:
    match = section_re.search(output)
    if not match:
        return ""
    tail = output[match.end() :]
    next_match = COMBINED_SECTION_RE.search(tail)
    return tail[: next_match.start()] if next_match else tail


def _has_meaningful_description(output: str) -> bool:
    lines = output.splitlines()
    usage_index = next((idx for idx, line in enumerate(lines) if "usage:" in line.lower()), -1)
    if usage_index < 0:
        return False
    for line in lines[usage_index + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if lowered in {"options:", "optional arguments:", "positional arguments:", "arguments:"}:
            break
        if OPTION_LINE_RE.match(stripped):
            continue
        if DESCRIPTION_PLACEHOLDER_RE.search(stripped):
            continue
        if len(re.findall(r"[A-Za-zА-Яа-я]", stripped)) >= 6:
            return True
    return False


def _has_arguments_listing(output: str) -> bool:
    if OPTIONS_HEADING_RE.search(output):
        return True
    return bool(OPTION_LINE_RE.search(output))


def _has_exit_code_details(output: str) -> bool:
    section = _extract_section_window(output, EXIT_CODES_RE)
    if not section:
        return False
    has_zero = bool(re.search(r"(?<!\d)0(?!\d)", section))
    has_non_zero = bool(
        re.search(r"(?<!\d)[1-9](?!\d)", section) or re.search(r"\b(non[-\s]?zero|error|failure)\b", section, re.IGNORECASE)
    )
    return has_zero and has_non_zero


def _string_constant(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _action_help_suppressed(call: ast.Call) -> bool:
    for keyword in call.keywords:
        if keyword.arg != "help":
            continue
        value = keyword.value
        if isinstance(value, ast.Attribute) and value.attr == "SUPPRESS":
            return True
    return False


def _collect_declared_options(source_text: str) -> set[str]:
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return set()

    options: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = ""
        if isinstance(func, ast.Attribute):
            func_name = func.attr
        elif isinstance(func, ast.Name):
            func_name = func.id
        if func_name != "add_argument":
            continue
        if _action_help_suppressed(node):
            continue
        for arg in node.args:
            value = _string_constant(arg)
            if value and value.startswith("-"):
                options.add(value)
                continue
            if isinstance(arg, (ast.List, ast.Tuple)):
                for element in arg.elts:
                    opt = _string_constant(element)
                    if opt and opt.startswith("-"):
                        options.add(opt)
    return options


def _collect_help_options(output: str) -> set[str]:
    options: set[str] = set()
    for line in output.splitlines():
        if not OPTION_LINE_RE.match(line):
            continue
        for option in HELP_OPTION_RE.findall(line):
            if option.startswith("-"):
                options.add(option)
    return options


def _check_help_contract(path: Path, output: str, source_text: str) -> list[str]:
    rel = path.as_posix()
    errors: list[str] = []
    if not USAGE_RE.search(output):
        errors.append(f"{rel}: --help output must include usage")
        return errors
    if not _has_meaningful_description(output):
        errors.append(f"{rel}: --help output must include a meaningful command description")
    if not _has_arguments_listing(output):
        errors.append(f"{rel}: --help output must list arguments/options")
    if not EXAMPLES_RE.search(output):
        errors.append(f"{rel}: --help output must include an Examples section")
    if not OUTPUTS_RE.search(output):
        errors.append(f"{rel}: --help output must include an Outputs section")
    if not EXIT_CODES_RE.search(output):
        errors.append(f"{rel}: --help output must include an Exit codes section")
    elif not _has_exit_code_details(output):
        errors.append(f"{rel}: Exit codes section must describe code 0 and at least one non-zero code")

    if ARGPARSE_RE.search(source_text):
        declared_options = _collect_declared_options(source_text)
        if declared_options:
            help_options = _collect_help_options(output)
            ignored = {"-h", "--help"}
            missing_in_help = sorted(opt for opt in declared_options - help_options if opt not in ignored)
            if missing_in_help:
                sample = ", ".join(missing_in_help[:6])
                if len(missing_in_help) > 6:
                    sample += ", ..."
                errors.append(f"{rel}: --help missing declared argparse options ({sample})")

            unknown_in_code = sorted(opt for opt in help_options - declared_options if opt not in ignored)
            if unknown_in_code:
                sample = ", ".join(unknown_in_code[:6])
                if len(unknown_in_code) > 6:
                    sample += ", ..."
                errors.append(f"{rel}: --help lists options not declared in source ({sample})")
    return errors


def run_checks(repo_root: Path) -> CheckResult:
    errors: list[str] = []
    warnings: list[str] = []

    runtime_paths = _iter_runtime_paths(repo_root)
    cli_count = 0
    library_count = 0

    for path in runtime_paths:
        rel = path.relative_to(repo_root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{rel}: failed to read runtime file ({exc})")
            continue

        signals = _hook_signals(text)
        if signals:
            labels = ", ".join(signals)
            errors.append(f"{rel}: hook-runtime signal in skills runtime ({labels})")

        if not _is_cli_entrypoint(text):
            library_count += 1
            continue
        cli_count += 1

        rc, output, timed_out = _run_help(repo_root, path)
        if timed_out:
            errors.append(f"{rel}: --help timed out")
            continue
        if rc != 0:
            snippet = output.splitlines()[0] if output else "no output"
            errors.append(f"{rel}: --help exited with {rc} ({snippet})")
            continue

        errors.extend(_check_help_contract(Path(rel), output, text))

    return CheckResult(
        errors=errors,
        warnings=warnings,
        total_runtime=len(runtime_paths),
        cli_entrypoints=cli_count,
        library_runtime=library_count,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate strict CLI adapter contract for skill runtime entrypoints.")
    parser.add_argument("--root", default=str(ROOT), help="Repository root (default: auto-detected).")
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Treat warnings as fatal errors (exit 2).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.root).expanduser().resolve()
    result = run_checks(repo_root)

    print(
        "[cli-adapter-guard] SUMMARY: "
        f"runtime={result.total_runtime} cli={result.cli_entrypoints} library={result.library_runtime} "
        f"errors={len(result.errors)} warnings={len(result.warnings)}"
    )

    for message in result.warnings:
        print(f"[cli-adapter-guard] WARN: {message}", file=sys.stderr)
    for message in result.errors:
        print(f"[cli-adapter-guard] ERROR: {message}", file=sys.stderr)

    if result.errors:
        return 2
    if args.fail_on_warn and result.warnings:
        print("[cli-adapter-guard] ERROR: warnings promoted to errors (--fail-on-warn).", file=sys.stderr)
        return 2
    print("[cli-adapter-guard] OK")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

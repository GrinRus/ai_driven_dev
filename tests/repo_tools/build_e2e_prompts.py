#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRAGMENTS_DIR = ROOT / "tests" / "repo_tools" / "e2e_prompt"
PROMPT_SPECS_PATH = FRAGMENTS_DIR / "prompt_specs.json"
INCLUDE_PATTERN = re.compile(r"\{\{INCLUDE:([^}]+)\}\}")


@dataclass(frozen=True)
class PromptSpec:
    prompt_code: str
    prompt_title: str
    base_path: Path
    must_read_path: Path
    must_read_extra: tuple[str, ...]
    profiles: dict[str, Path]
    outputs: dict[str, Path]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_with_includes(path: Path, *, seen: tuple[Path, ...] = ()) -> str:
    if path in seen:
        cycle = " -> ".join(str(item.relative_to(ROOT)) for item in (*seen, path))
        raise ValueError(f"Include cycle detected: {cycle}")
    text = _read(path)
    current_seen = (*seen, path)

    def _replace(match: re.Match[str]) -> str:
        include_path = (FRAGMENTS_DIR / match.group(1).strip()).resolve()
        try:
            include_path.relative_to(FRAGMENTS_DIR.resolve())
        except ValueError as exc:
            raise ValueError(f"Include path escapes prompt fragments dir: {include_path}") from exc
        return _read_with_includes(include_path, seen=current_seen).rstrip("\n")

    return INCLUDE_PATTERN.sub(_replace, text)


def _normalize(text: str) -> str:
    return text.strip() + "\n"


def _load_prompt_specs() -> dict[str, PromptSpec]:
    payload = json.loads(PROMPT_SPECS_PATH.read_text(encoding="utf-8"))
    return {
        prompt_code: PromptSpec(
            prompt_code=prompt_code,
            prompt_title=str(raw["prompt_title"]),
            base_path=ROOT / str(raw["base_path"]),
            must_read_path=ROOT / str(raw["must_read_path"]),
            must_read_extra=tuple(str(item) for item in raw.get("must_read_extra", [])),
            profiles={name: ROOT / str(path) for name, path in raw["profiles"].items()},
            outputs={name: ROOT / str(path) for name, path in raw["outputs"].items()},
        )
        for prompt_code, raw in payload.items()
    }


def _render_must_read(template: str, extra_items: tuple[str, ...]) -> str:
    extra_block = "\n".join(f"- `{item}`" for item in extra_items)
    return template.replace("{{EXTRA_MUST_READ}}", extra_block).replace("\n\n\n", "\n\n").strip()


def _render(
    *,
    spec: PromptSpec,
    profile_title: str,
    profile_body: str,
    must_read: str,
    base_template: str,
) -> str:
    body = profile_body.replace("{{MUST_READ_MANIFEST}}", must_read.strip())
    rendered = (
        base_template.replace("{{PROMPT_TITLE}}", spec.prompt_title)
        .replace("{{PROMPT_CODE}}", spec.prompt_code)
        .replace("{{PROFILE_TITLE}}", profile_title)
        .replace("{{PROFILE_BODY}}", body.strip())
    )
    return _normalize(rendered)


def build() -> dict[Path, str]:
    rendered: dict[Path, str] = {}
    for spec in _load_prompt_specs().values():
        base_template = _read_with_includes(spec.base_path)
        must_read = _render_must_read(_read_with_includes(spec.must_read_path), spec.must_read_extra)
        profile_names = set(spec.profiles)
        output_names = set(spec.outputs)
        if profile_names != output_names:
            missing_profiles = sorted(output_names - profile_names)
            missing_outputs = sorted(profile_names - output_names)
            problems = []
            if missing_profiles:
                problems.append(f"missing profiles for outputs: {missing_profiles}")
            if missing_outputs:
                problems.append(f"missing outputs for profiles: {missing_outputs}")
            raise ValueError("; ".join(problems))
        for profile_title, profile_path in spec.profiles.items():
            rendered[spec.outputs[profile_title]] = _render(
                spec=spec,
                profile_title=profile_title,
                profile_body=_read_with_includes(profile_path),
                must_read=must_read,
                base_template=base_template,
            )
    return rendered


def write_outputs(rendered: dict[Path, str]) -> None:
    for output_path, text in rendered.items():
        output_path.write_text(text, encoding="utf-8")
        print(f"[e2e-prompt-build] wrote {output_path}")


def check_outputs(rendered: dict[Path, str]) -> int:
    failed = False
    for output_path, expected in rendered.items():
        actual = _read(output_path) if output_path.exists() else ""
        if actual != expected:
            failed = True
            print(f"[e2e-prompt-build] OUT-OF-DATE: {output_path}")
            diff = difflib.unified_diff(
                actual.splitlines(),
                expected.splitlines(),
                fromfile=f"{output_path} (actual)",
                tofile=f"{output_path} (expected)",
                lineterm="",
            )
            for line in list(diff)[:200]:
                print(line)
    if failed:
        return 1
    print("[e2e-prompt-build] outputs are up to date")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AIDD E2E prompt files from shared contract fragments")
    parser.add_argument("--check", action="store_true", help="Fail if generated outputs differ")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rendered = build()
    if args.check:
        return check_outputs(rendered)
    write_outputs(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

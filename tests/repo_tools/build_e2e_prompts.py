#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRAGMENTS_DIR = ROOT / "tests" / "repo_tools" / "e2e_prompt"


@dataclass(frozen=True)
class PromptSpec:
    base_path: Path
    must_read_path: Path
    profiles: dict[str, Path]
    outputs: dict[str, Path]


PROMPT_SPECS = {
    "TST-001": PromptSpec(
        base_path=FRAGMENTS_DIR / "base_contract.md",
        must_read_path=FRAGMENTS_DIR / "must_read_manifest.md",
        profiles={
            "FULL": FRAGMENTS_DIR / "profile_full.md",
            "SMOKE": FRAGMENTS_DIR / "profile_smoke.md",
        },
        outputs={
            "FULL": ROOT / "docs" / "e2e" / "aidd_test_flow_prompt_ralph_script_full.txt",
            "SMOKE": ROOT / "docs" / "e2e" / "aidd_test_flow_prompt_ralph_script.txt",
        },
    ),
    "TST-002": PromptSpec(
        base_path=FRAGMENTS_DIR / "quality_base_contract.md",
        must_read_path=FRAGMENTS_DIR / "quality_must_read_manifest.md",
        profiles={
            "FULL": FRAGMENTS_DIR / "quality_profile_full.md",
        },
        outputs={
            "FULL": ROOT / "docs" / "e2e" / "aidd_test_quality_audit_prompt_tst002_full.txt",
        },
    ),
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalize(text: str) -> str:
    return text.strip() + "\n"


def _render(profile_title: str, profile_body: str, must_read: str, base_template: str) -> str:
    body = profile_body.replace("{{MUST_READ_MANIFEST}}", must_read.strip())
    rendered = base_template.replace("{{PROFILE_TITLE}}", profile_title).replace("{{PROFILE_BODY}}", body.strip())
    return _normalize(rendered)


def build() -> dict[Path, str]:
    rendered: dict[Path, str] = {}
    for spec in PROMPT_SPECS.values():
        base_template = _read(spec.base_path)
        must_read = _read(spec.must_read_path)
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
                profile_title=profile_title,
                profile_body=_read(profile_path),
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
    parser = argparse.ArgumentParser(description="Build AIDD E2E prompt files from 2-layer fragments")
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

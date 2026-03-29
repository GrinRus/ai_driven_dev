#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRAGMENTS_DIR = ROOT / "tests" / "repo_tools" / "e2e_prompt"
MUST_READ_PATH = FRAGMENTS_DIR / "must_read_manifest.md"

PROMPT_FAMILIES = {
    "audit": {
        "base": FRAGMENTS_DIR / "base_contract.md",
        "profiles": {
            "FULL": FRAGMENTS_DIR / "profile_full.md",
            "SMOKE": FRAGMENTS_DIR / "profile_smoke.md",
        },
        "outputs": {
            "FULL": ROOT / "docs" / "e2e" / "aidd_test_flow_prompt_ralph_script_full.txt",
            "SMOKE": ROOT / "docs" / "e2e" / "aidd_test_flow_prompt_ralph_script.txt",
        },
    },
    "quality": {
        "base": FRAGMENTS_DIR / "quality_base_contract.md",
        "profiles": {
            "FULL": FRAGMENTS_DIR / "quality_profile_full.md",
            "SMOKE": FRAGMENTS_DIR / "quality_profile_smoke.md",
        },
        "outputs": {
            "FULL": ROOT / "docs" / "e2e" / "aidd_quality_audit_prompt_ralph_script_full.txt",
            "SMOKE": ROOT / "docs" / "e2e" / "aidd_quality_audit_prompt_ralph_script.txt",
        },
    },
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
    must_read = _read(MUST_READ_PATH)
    rendered: dict[Path, str] = {}
    for family in PROMPT_FAMILIES.values():
        base_template = _read(family["base"])
        profile_paths: dict[str, Path] = family["profiles"]
        output_paths: dict[str, Path] = family["outputs"]
        for profile_title, profile_path in profile_paths.items():
            rendered[output_paths[profile_title]] = _render(
                profile_title=profile_title,
                profile_body=_read(profile_path),
                must_read=must_read,
                base_template=base_template,
            )
    return rendered


def write_outputs(rendered: dict[Path, str]) -> None:
    for output_path in sorted(rendered, key=lambda item: item.as_posix()):
        output_path.write_text(rendered[output_path], encoding="utf-8")
        print(f"[e2e-prompt-build] wrote {output_path}")


def check_outputs(rendered: dict[Path, str]) -> int:
    failed = False
    for output_path in sorted(rendered, key=lambda item: item.as_posix()):
        expected = rendered[output_path]
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

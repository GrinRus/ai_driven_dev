#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Sequence, Tuple


STREAM_SUFFIX_RE = re.compile(r"\.stream\.(?:jsonl|log)$", re.IGNORECASE)
STREAM_TOKEN_RE = re.compile(r"([^\s\"']+\.stream\.(?:jsonl|log))", re.IGNORECASE)
HEADER_KV_RE = re.compile(r"\b(stream|log)=([^\s\"']+)", re.IGNORECASE)
TRAILING_PUNCT_RE = re.compile(r"[),.;:\]]+$")


@dataclass(frozen=True)
class CandidatePath:
    source: str
    raw_path: str


@dataclass(frozen=True)
class ResolvedPath:
    source: str
    path: str


def _iter_strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)


def _extract_tokens(text: str) -> List[str]:
    return [match for match in STREAM_TOKEN_RE.findall(text or "")]


def _clean_raw_token(token: str) -> str:
    value = str(token or "").strip().strip("'\"")
    if value.startswith("stream="):
        value = value[len("stream=") :]
    elif value.startswith("log="):
        value = value[len("log=") :]
    value = TRAILING_PUNCT_RE.sub("", value)
    return value.strip()


def extract_primary_paths(log_path: Path, project_dir: Path) -> List[CandidatePath]:
    del project_dir  # kept for API parity
    candidates: List[CandidatePath] = []
    if not log_path.exists():
        return candidates

    for raw in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue

        if line.startswith("{"):
            try:
                event = json.loads(line)
            except Exception:
                event = None
            if isinstance(event, dict) and event.get("type") == "system" and event.get("subtype") == "init":
                for value in _iter_strings(event):
                    for token in _extract_tokens(value):
                        candidates.append(CandidatePath(source="init_json", raw_path=token))
                continue

        if line.startswith("==>") and "streaming enabled:" in line:
            for _, value in HEADER_KV_RE.findall(line):
                if STREAM_SUFFIX_RE.search(value):
                    candidates.append(CandidatePath(source="loop_stream_header", raw_path=value))

    return candidates


def normalize_and_validate(
    candidates: Sequence[CandidatePath],
    project_dir: Path,
) -> Tuple[List[ResolvedPath], List[ResolvedPath], List[ResolvedPath]]:
    project_abs = project_dir.resolve()
    valid: List[ResolvedPath] = []
    invalid: List[ResolvedPath] = []
    missing: List[ResolvedPath] = []
    seen: set[str] = set()

    for candidate in candidates:
        cleaned = _clean_raw_token(candidate.raw_path)
        if not cleaned:
            continue
        path = Path(cleaned)
        if not path.is_absolute():
            path = project_abs / path
        abs_path = path.resolve()
        key = f"{candidate.source}:{abs_path}"
        if key in seen:
            continue
        seen.add(key)

        abs_str = str(abs_path)
        try:
            abs_path.relative_to(project_abs)
            in_project = True
        except ValueError:
            in_project = False

        resolved = ResolvedPath(source=candidate.source, path=abs_str)
        if not in_project:
            invalid.append(resolved)
        elif abs_path.exists():
            valid.append(resolved)
        else:
            missing.append(resolved)

    return valid, invalid, missing


def _iter_fallback_candidates(loop_root: Path) -> Iterator[Path]:
    if not loop_root.exists():
        return
    for pattern in ("*.stream.jsonl", "*.stream.log"):
        for path in loop_root.rglob(pattern):
            if path.is_file():
                yield path.resolve()


def fallback_discovery(
    project_dir: Path,
    ticket: str,
    run_start_epoch: int,
    *,
    max_paths: int = 4,
    freshness_epsilon_seconds: int = 5,
) -> List[CandidatePath]:
    project_abs = project_dir.resolve()
    normalized_ticket = str(ticket or "").strip()
    if not normalized_ticket:
        # Prevent cross-ticket contamination when caller did not provide ticket.
        return []
    loop_root = project_abs / "aidd" / "reports" / "loops" / normalized_ticket

    floor = max(int(run_start_epoch) - int(freshness_epsilon_seconds), 0)
    candidates: List[tuple[float, Path]] = []
    for path in _iter_fallback_candidates(loop_root):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < floor:
            continue
        candidates.append((mtime, path))

    candidates.sort(key=lambda item: (item[0], str(item[1])), reverse=True)
    selected = candidates[: max(max_paths, 0)]
    return [CandidatePath(source="fallback_scan", raw_path=str(path)) for _, path in selected]


def write_stream_paths_report(
    out_path: Path,
    valid: Sequence[ResolvedPath],
    invalid: Sequence[ResolvedPath],
    missing: Sequence[ResolvedPath],
    used_fallback: bool,
    cli_not_emitted: bool,
) -> None:
    lines: List[str] = []
    for entry in valid:
        lines.append(f"source={entry.source} path={entry.path}")
    for entry in invalid:
        lines.append(f"source={entry.source} stream_path_invalid={entry.path}")
    for entry in missing:
        lines.append(f"source={entry.source} stream_path_missing={entry.path}")
    if used_fallback:
        lines.append("fallback_scan=1")
    if cli_not_emitted:
        lines.append("stream_path_not_emitted_by_cli=1")
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def resolve_stream_paths(
    *,
    log_path: Path,
    out_path: Path,
    project_dir: Path,
    ticket: str,
    run_start_epoch: int,
) -> dict:
    primary_candidates = extract_primary_paths(log_path=log_path, project_dir=project_dir)
    valid, invalid, missing = normalize_and_validate(primary_candidates, project_dir=project_dir)

    used_fallback = False
    if not valid:
        fallback_candidates = fallback_discovery(
            project_dir=project_dir,
            ticket=ticket,
            run_start_epoch=run_start_epoch,
        )
        fb_valid, fb_invalid, fb_missing = normalize_and_validate(fallback_candidates, project_dir=project_dir)
        used_fallback = True
        valid = fb_valid
        invalid = list(invalid) + list(fb_invalid)
        missing = list(missing) + list(fb_missing)

    cli_not_emitted = not bool(valid)
    write_stream_paths_report(
        out_path=out_path,
        valid=valid,
        invalid=invalid,
        missing=missing,
        used_fallback=used_fallback,
        cli_not_emitted=cli_not_emitted,
    )
    return {
        "primary_candidates": len(primary_candidates),
        "valid_count": len(valid),
        "invalid_count": len(invalid),
        "missing_count": len(missing),
        "used_fallback": int(used_fallback),
        "cli_not_emitted": int(cli_not_emitted),
        "valid_paths": [item.path for item in valid],
    }

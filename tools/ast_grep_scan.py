from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

AST_GREP_SCHEMA = "aidd.ast_grep_match.v1"

LANG_EXTS = {
    "kt": {".kt"},
    "kts": {".kts"},
    "java": {".java"},
    "js": {".js", ".jsx"},
    "ts": {".ts", ".tsx"},
    "py": {".py"},
}

DEFAULT_EXTENSIONS = sorted({ext for exts in LANG_EXTS.values() for ext in exts})


@dataclass(frozen=True)
class AstGrepConfig:
    enabled: bool
    required_for_langs: list[str]
    max_files: int
    max_matches: int
    timeout_s: int
    batch_size: int


def _load_config(root: Path) -> AstGrepConfig:
    config_path = root / "config" / "conventions.json"
    data = {}
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    researcher = data.get("researcher") if isinstance(data, dict) else {}
    ast_cfg = researcher.get("ast_grep") if isinstance(researcher, dict) else {}
    if not isinstance(ast_cfg, dict):
        ast_cfg = {}
    return AstGrepConfig(
        enabled=bool(ast_cfg.get("enabled", False)),
        required_for_langs=[str(item).lower() for item in ast_cfg.get("required_for_langs", []) if item],
        max_files=int(ast_cfg.get("max_files", 400)),
        max_matches=int(ast_cfg.get("max_matches", 300)),
        timeout_s=int(ast_cfg.get("timeout_s", 60)),
        batch_size=int(ast_cfg.get("batch_size", 120)),
    )


def _detect_langs(paths: Iterable[Path]) -> set[str]:
    detected: set[str] = set()
    for path in paths:
        suffix = path.suffix.lower()
        for lang, exts in LANG_EXTS.items():
            if suffix in exts:
                detected.add(lang)
    return detected


def _iter_files(paths: Sequence[Path], *, max_files: int) -> List[Path]:
    files: List[Path] = []
    for root in paths:
        if max_files and len(files) >= max_files:
            break
        if root.is_dir():
            try:
                iterator = root.rglob("*")
            except OSError:
                continue
            try:
                for path in iterator:
                    if max_files and len(files) >= max_files:
                        break
                    if not path.is_file():
                        continue
                    if path.suffix.lower() not in DEFAULT_EXTENSIONS:
                        continue
                    files.append(path)
            except OSError:
                continue
        elif root.is_file():
            if root.suffix.lower() in DEFAULT_EXTENSIONS:
                files.append(root)
    return files


def _find_binary() -> Optional[str]:
    return shutil.which("sg") or shutil.which("ast-grep")


def _parse_json_payload(text: str) -> list[dict]:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    matches: list[dict] = []
    for line in lines:
        try:
            matches.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    if matches:
        return matches
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def _has_rule_files(rule_dir: Path) -> bool:
    if not rule_dir.is_dir():
        return False
    for pattern in ("*.yaml", "*.yml"):
        if any(rule_dir.rglob(pattern)):
            return True
    return False


def _split_ruleset(text: str) -> List[str]:
    lines = text.splitlines()
    blocks: List[List[str]] = []
    current: List[str] = []
    in_rules = False
    for raw in lines:
        stripped = raw.strip()
        if stripped == "---":
            continue
        if not in_rules:
            if stripped == "rules:":
                in_rules = True
            continue
        if raw.startswith("  - "):
            if current:
                blocks.append(current)
                current = []
            current.append(raw[4:])
            continue
        if raw.startswith("    "):
            current.append(raw[4:])
    if current:
        blocks.append(current)
    return ["\n".join(block).rstrip() + "\n" for block in blocks if block]


def _rule_id_from_block(block: str) -> Optional[str]:
    for line in block.splitlines():
        if line.startswith("id:"):
            return line.split(":", 1)[1].strip()
    return None


def _expand_ruleset_files(rule_files: Sequence[Path]) -> Tuple[List[Path], Optional[tempfile.TemporaryDirectory]]:
    expanded: List[Path] = []
    temp_dir: Optional[tempfile.TemporaryDirectory] = None
    for rule_file in rule_files:
        try:
            text = rule_file.read_text(encoding="utf-8")
        except OSError:
            continue
        if "rules:" not in text:
            expanded.append(rule_file)
            continue
        blocks = _split_ruleset(text)
        if not blocks:
            continue
        if temp_dir is None:
            temp_dir = tempfile.TemporaryDirectory(prefix="aidd-ast-grep-rules-")
        for idx, block in enumerate(blocks, start=1):
            rule_id = _rule_id_from_block(block) or f"rule-{idx}"
            safe_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in rule_id)[:80]
            filename = f"{rule_file.stem}-{safe_id}.yaml"
            dest = Path(temp_dir.name) / filename
            dest.write_text(block, encoding="utf-8")
            expanded.append(dest)
    return expanded, temp_dir


def _gather_rule_files(rule_dirs: Sequence[Path]) -> List[Path]:
    files: List[Path] = []
    seen: set[Path] = set()
    for rule_dir in rule_dirs:
        for pattern in ("*.yaml", "*.yml"):
            for path in sorted(rule_dir.rglob(pattern)):
                if path in seen:
                    continue
                seen.add(path)
                files.append(path)
    return files


def _normalize_match(raw: dict) -> dict:
    rule_id = raw.get("rule_id") or raw.get("ruleId") or (raw.get("rule") or {}).get("id")
    path = raw.get("path") or raw.get("file") or raw.get("filename") or raw.get("filepath")
    line = raw.get("line")
    col = raw.get("col") or raw.get("column")
    range_info = raw.get("range") or {}
    if line is None and isinstance(range_info, dict):
        start = range_info.get("start") or {}
        line = start.get("line")
        col = col or start.get("column")
    snippet = raw.get("snippet") or raw.get("text") or (raw.get("node") or {}).get("text") or ""
    message = raw.get("message") or raw.get("reason") or ""
    tags = raw.get("tags") or (raw.get("rule") or {}).get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    return {
        "schema": AST_GREP_SCHEMA,
        "rule_id": rule_id,
        "path": path,
        "line": line,
        "col": col,
        "snippet": snippet[:240] if isinstance(snippet, str) else snippet,
        "message": message,
        "tags": tags,
    }


def _select_rule_dirs(rules_root: Path, tags: Sequence[str]) -> List[Path]:
    if not rules_root.exists():
        return []
    available = sorted([path for path in rules_root.iterdir() if _has_rule_files(path)])
    if not available:
        return []
    tag_set = {str(tag).strip().lower() for tag in tags if tag and str(tag).strip()}
    if tag_set:
        selected: List[Path] = []
        for pack in ("custom", "common"):
            candidate = rules_root / pack
            if _has_rule_files(candidate):
                selected.append(candidate)
        for tag in sorted(tag_set):
            candidate = rules_root / tag
            if _has_rule_files(candidate) and candidate not in selected:
                selected.append(candidate)
        if selected:
            return selected
    return available


def _run_scan(cmd: list[str], *, timeout_s: int) -> tuple[Optional[list[dict]], dict]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except Exception as exc:
        return None, {"reason": "scan-failed", "error": str(exc)}

    if result.returncode not in (0, 1):
        stderr = (result.stderr or "").strip()
        if stderr and len(stderr) > 400:
            stderr = stderr[:400].rstrip() + "…"
        payload = {"reason": "scan-failed", "returncode": result.returncode}
        if stderr:
            payload["stderr"] = stderr
        return None, payload

    return _parse_json_payload(result.stdout), {"returncode": result.returncode}


def scan_ast_grep(
    root: Path,
    *,
    ticket: str,
    search_roots: Sequence[Path],
    output: Path,
    tags: Optional[Sequence[str]] = None,
) -> tuple[Optional[Path], dict]:
    cfg = _load_config(root)
    files = _iter_files(search_roots, max_files=cfg.max_files)
    detected_langs = _detect_langs(files)
    if cfg.required_for_langs:
        if not (set(cfg.required_for_langs) & detected_langs):
            return None, {"reason": "langs-not-required"}
    if not cfg.enabled and not cfg.required_for_langs:
        return None, {"reason": "disabled"}
    if not files:
        return None, {"reason": "no-files"}

    binary = _find_binary()
    if not binary:
        return None, {"reason": "binary-missing"}

    rules_root = root / "ast-grep" / "rules"
    rule_dirs = _select_rule_dirs(rules_root, tags or [])
    if not rule_dirs:
        return None, {"reason": "rules-missing"}

    rule_files = _gather_rule_files(rule_dirs)
    rule_files, temp_dir = _expand_ruleset_files(rule_files)
    if not rule_files:
        return None, {"reason": "rules-missing"}

    batch_size = cfg.batch_size if cfg.batch_size > 0 else len(files)
    if batch_size <= 0:
        batch_size = len(files) or 1

    matches: list[dict] = []
    scan_meta: dict = {"batches": 0, "rules_total": len(rule_files), "rules_scanned": 0}
    scan_failed: dict | None = None
    for rule_file in rule_files:
        rule_batches = 0
        for idx in range(0, len(files), batch_size):
            chunk = files[idx : idx + batch_size]
            cmd = [binary, "scan", "-r", str(rule_file), "--json"] + [str(path) for path in chunk]
            parsed, meta = _run_scan(cmd, timeout_s=cfg.timeout_s)
            if parsed is None:
                meta["rule"] = str(rule_file)
                scan_failed = meta
                break
            scan_meta["batches"] = scan_meta.get("batches", 0) + 1
            rule_batches += 1
            matches.extend(parsed)
            if cfg.max_matches and len(matches) >= cfg.max_matches:
                break
        scan_meta["rules_scanned"] = scan_meta.get("rules_scanned", 0) + 1
        if scan_failed or (cfg.max_matches and len(matches) >= cfg.max_matches):
            break

    if scan_failed:
        return None, scan_failed
    normalized: list[dict] = []
    truncated = False
    for raw in matches:
        if cfg.max_matches and len(normalized) >= cfg.max_matches:
            truncated = True
            break
        normalized.append(_normalize_match(raw))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for item in normalized:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    stats = {
        "matches_total": len(matches),
        "matches_written": len(normalized),
        "truncated": truncated,
        "schema": AST_GREP_SCHEMA,
        "rule_packs": [path.name for path in rule_dirs],
        "batches": scan_meta.get("batches", 0),
        "batch_size": batch_size,
    }
    return output, stats

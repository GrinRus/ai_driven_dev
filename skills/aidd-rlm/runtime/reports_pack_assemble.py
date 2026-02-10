#!/usr/bin/env python3
"""Deterministic pack assembly helpers for reports_pack."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from aidd_runtime import runtime
from aidd_runtime.rlm_config import file_id_for_path, load_rlm_settings
from aidd_runtime import reports_pack as core


def truncate_list(items: Iterable[Any], limit: int) -> List[Any]:
    if limit <= 0:
        return []
    return list(items)[:limit]


def truncate_text(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip()


def extract_evidence_snippet(
    root: Optional[Path],
    evidence_ref: Dict[str, Any],
    *,
    max_chars: int,
) -> str:
    if not root or not evidence_ref:
        return ""
    raw_path = evidence_ref.get("path")
    if not raw_path:
        return ""
    path = Path(str(raw_path))
    abs_path = path if path.is_absolute() else (root / path)
    if not abs_path.exists() and root.name == "aidd":
        alt_path = root.parent / path
        if alt_path.exists():
            abs_path = alt_path
    if not abs_path.exists():
        return ""
    try:
        lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    try:
        line_start = int(evidence_ref.get("line_start") or 0)
        line_end = int(evidence_ref.get("line_end") or line_start)
    except (TypeError, ValueError):
        return ""
    if line_start <= 0 or line_end <= 0:
        return ""
    start_idx = max(0, line_start - 1)
    end_idx = max(start_idx, line_end - 1)
    snippet = "\n".join(lines[start_idx : end_idx + 1]).strip()
    normalized = " ".join(snippet.split())
    return truncate_text(normalized, max_chars)


def stable_id(*parts: Any) -> str:
    digest = hashlib.sha1()
    for part in parts:
        digest.update(str(part).encode("utf-8"))
        digest.update(b"|")
    return digest.hexdigest()[:12]


def columnar(cols: List[str], rows: List[List[Any]]) -> Dict[str, Any]:
    return {
        "cols": cols,
        "rows": rows,
    }


def pack_paths(entries: Iterable[Any], limit: int, sample_limit: int) -> List[Dict[str, Any]]:
    packed: List[Dict[str, Any]] = []
    for entry in truncate_list(entries, limit):
        if not isinstance(entry, dict):
            continue
        samples = entry.get("sample") or []
        packed.append(
            {
                "path": entry.get("path"),
                "type": entry.get("type"),
                "exists": entry.get("exists"),
                "sample": truncate_list(samples, sample_limit),
            }
        )
    return packed


def pack_matches(entries: Iterable[Any], limit: int, snippet_limit: int) -> Dict[str, Any]:
    cols = ["id", "token", "file", "line", "snippet"]
    rows: List[List[Any]] = []
    for entry in truncate_list(entries, limit):
        if not isinstance(entry, dict):
            continue
        token = str(entry.get("token") or "").strip()
        file_path = str(entry.get("file") or "").strip()
        line = entry.get("line")
        snippet = truncate_text(str(entry.get("snippet") or ""), snippet_limit)
        if not file_path:
            continue
        rows.append([stable_id(file_path, line, token), token, file_path, line, snippet])
    return columnar(cols, rows)


def pack_reuse(entries: Iterable[Any], limit: int) -> Dict[str, Any]:
    cols = ["id", "path", "language", "score", "has_tests", "top_symbols", "imports"]
    rows: List[List[Any]] = []
    for entry in truncate_list(entries, limit):
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "").strip()
        if not path:
            continue
        score = entry.get("score")
        rows.append(
            [
                stable_id(path, score, entry.get("language")),
                path,
                entry.get("language"),
                score,
                entry.get("has_tests"),
                truncate_list(entry.get("top_symbols") or [], 3),
                truncate_list(entry.get("imports") or [], 5),
            ]
        )
    return columnar(cols, rows)


def pack_findings(entries: Iterable[Any], limit: int, cols: List[str]) -> Dict[str, Any]:
    rows: List[List[Any]] = []
    for entry in truncate_list(entries, limit):
        if not isinstance(entry, dict):
            continue
        rows.append([entry.get(col) for col in cols])
    return columnar(cols, rows)


def pack_tests_executed(entries: Iterable[Any], limit: int) -> Dict[str, Any]:
    cols = ["command", "status", "log", "exit_code"]
    rows: List[List[Any]] = []
    for entry in truncate_list(entries, limit):
        if not isinstance(entry, dict):
            continue
        rows.append(
            [
                entry.get("command"),
                entry.get("status"),
                entry.get("log") or entry.get("log_path"),
                entry.get("exit_code"),
            ]
        )
    return columnar(cols, rows)


def load_rlm_links_stats(root: Path, ticket: str) -> Optional[Dict[str, Any]]:
    path = root / "reports" / "research" / f"{ticket}-rlm.links.stats.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def rlm_link_warnings(stats: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    if "links_total" in stats and int(stats.get("links_total") or 0) == 0:
        warnings.append("rlm_links_empty_warn")
    if stats.get("links_truncated"):
        warnings.append("rlm links truncated: max_links reached")
    if int(stats.get("target_files_trimmed") or 0) > 0:
        warnings.append("rlm link targets trimmed: max_files reached")
    if int(stats.get("symbols_truncated") or 0) > 0:
        warnings.append("rlm link symbols truncated: max_symbols_per_file reached")
    if int(stats.get("candidate_truncated") or 0) > 0:
        warnings.append("rlm link candidates truncated: max_definition_hits_per_symbol reached")
    if int(stats.get("rg_timeouts") or 0) > 0:
        warnings.append("rlm rg timeout during link search")
    if int(stats.get("rg_errors") or 0) > 0:
        warnings.append("rlm rg errors during link search")
    if "target_files_total" in stats and int(stats.get("target_files_total") or 0) == 0:
        warnings.append("rlm link targets empty")
    return warnings


def pack_rlm_nodes(nodes: Iterable[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    packed: List[Dict[str, Any]] = []
    for node in truncate_list(nodes, limit):
        if not isinstance(node, dict):
            continue
        packed.append(
            {
                "file_id": node.get("file_id") or node.get("id"),
                "path": node.get("path"),
                "summary": node.get("summary"),
                "framework_roles": node.get("framework_roles") or [],
                "test_hooks": node.get("test_hooks") or [],
                "risks": node.get("risks") or [],
            }
        )
    return packed


def pack_rlm_links(
    links: Iterable[Dict[str, Any]],
    *,
    limit: int,
    root: Optional[Path],
    snippet_chars: int,
) -> List[Dict[str, Any]]:
    packed: List[Dict[str, Any]] = []
    for link in truncate_list(links, limit):
        if not isinstance(link, dict):
            continue
        evidence_ref = link.get("evidence_ref") or {}
        snippet = extract_evidence_snippet(root, evidence_ref, max_chars=snippet_chars)
        packed.append(
            {
                "link_id": link.get("link_id"),
                "src_file_id": link.get("src_file_id"),
                "dst_file_id": link.get("dst_file_id"),
                "type": link.get("type"),
                "evidence_ref": evidence_ref,
                "evidence_snippet": snippet,
            }
        )
    return packed


def load_rlm_worklist_summary(
    root: Optional[Path],
    ticket: Optional[str],
    *,
    context: Optional[Dict[str, Any]] = None,
) -> tuple[Optional[str], Optional[int], Optional[Path]]:
    if not root or not ticket:
        return None, None, None
    worklist_path = None
    if context:
        raw = context.get("rlm_worklist_path")
        if isinstance(raw, str) and raw.strip():
            worklist_path = runtime.resolve_path_for_target(Path(raw), root)
    if worklist_path is None and ticket:
        worklist_path = core._find_pack_variant(root, f"{ticket}-rlm.worklist") or (
            root / "reports" / "research" / f"{ticket}-rlm.worklist.pack.json"
        )
    if not worklist_path or not worklist_path.exists():
        return None, None, worklist_path
    try:
        payload = json.loads(worklist_path.read_text(encoding="utf-8"))
    except Exception:
        return None, None, worklist_path
    if not isinstance(payload, dict):
        return None, None, worklist_path
    worklist_status = str(payload.get("status") or "").strip().lower() or None
    entries = payload.get("entries")
    worklist_entries = len(entries) if isinstance(entries, list) else None
    return worklist_status, worklist_entries, worklist_path


def build_research_pack(
    payload: Dict[str, Any],
    *,
    source_path: Optional[str] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    env_limits = core._env_limits().get("research") or {}
    lim = {**core.RESEARCH_LIMITS, **env_limits, **(limits or {})}

    profile = payload.get("profile") or {}
    recommendations = truncate_list(profile.get("recommendations") or [], lim["recommendations"])
    tests_evidence = truncate_list(profile.get("tests_evidence") or [], lim["tests_evidence"])
    suggested_test_tasks = truncate_list(profile.get("suggested_test_tasks") or [], lim["suggested_test_tasks"])
    manual_notes = truncate_list(payload.get("manual_notes") or [], lim["manual_notes"])
    rlm_warnings = truncate_list(payload.get("rlm_warnings") or [], lim["rlm_warnings"])

    packed = {
        "schema": core.SCHEMA,
        "pack_version": core.PACK_VERSION,
        "type": "research",
        "kind": "context",
        "ticket": payload.get("ticket"),
        "slug": payload.get("slug"),
        "slug_hint": payload.get("slug_hint"),
        "generated_at": payload.get("generated_at"),
        "source_path": source_path,
        "tags": truncate_list(payload.get("tags") or [], lim["tags"]),
        "keywords": truncate_list(payload.get("keywords") or [], lim["keywords"]),
        "keywords_raw": truncate_list(payload.get("keywords_raw") or [], lim["keywords_raw"]),
        "non_negotiables": truncate_list(payload.get("non_negotiables") or [], lim["non_negotiables"]),
        "paths": pack_paths(payload.get("paths") or [], lim["paths"], lim["path_samples"]),
        "paths_discovered": truncate_list(payload.get("paths_discovered") or [], lim["paths_discovered"]),
        "invalid_paths": truncate_list(payload.get("invalid_paths") or [], lim["invalid_paths"]),
        "docs": pack_paths(payload.get("docs") or [], lim["docs"], lim["path_samples"]),
        "profile": {
            "is_new_project": profile.get("is_new_project"),
            "src_layers": profile.get("src_layers") or [],
            "tests_detected": profile.get("tests_detected"),
            "tests_evidence": tests_evidence,
            "suggested_test_tasks": suggested_test_tasks,
            "config_detected": profile.get("config_detected"),
            "logging_artifacts": profile.get("logging_artifacts") or [],
            "recommendations": recommendations,
        },
        "manual_notes": manual_notes,
        "reuse_candidates": pack_reuse(payload.get("reuse_candidates") or [], lim["reuse_candidates"]),
        "matches": pack_matches(payload.get("matches") or [], lim["matches"], lim["match_snippet_chars"]),
        "rlm_targets_path": payload.get("rlm_targets_path"),
        "rlm_manifest_path": payload.get("rlm_manifest_path"),
        "rlm_worklist_path": payload.get("rlm_worklist_path"),
        "rlm_nodes_path": payload.get("rlm_nodes_path"),
        "rlm_links_path": payload.get("rlm_links_path"),
        "rlm_links_stats_path": payload.get("rlm_links_stats_path"),
        "rlm_pack_path": payload.get("rlm_pack_path"),
        "rlm_status": payload.get("rlm_status"),
        "rlm_warnings": rlm_warnings,
        "deep_mode": payload.get("deep_mode"),
        "auto_mode": payload.get("auto_mode"),
        "stats": {
            "matches": len(payload.get("matches") or []),
            "reuse_candidates": len(payload.get("reuse_candidates") or []),
        },
    }

    return packed


def build_research_context_pack(
    payload: Dict[str, Any],
    *,
    source_path: Optional[str] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    return build_research_pack(payload, source_path=source_path, limits=limits)


def build_qa_pack(
    payload: Dict[str, Any],
    *,
    source_path: Optional[str] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    env_limits = core._env_limits().get("qa") or {}
    lim = {**core.QA_LIMITS, **env_limits, **(limits or {})}
    findings = payload.get("findings") or []

    packed = {
        "schema": core.SCHEMA,
        "pack_version": core.PACK_VERSION,
        "type": "qa",
        "kind": "report",
        "ticket": payload.get("ticket"),
        "slug_hint": payload.get("slug_hint"),
        "generated_at": payload.get("generated_at"),
        "status": payload.get("status"),
        "summary": payload.get("summary"),
        "branch": payload.get("branch"),
        "source_path": source_path,
        "counts": payload.get("counts") or {},
        "findings": pack_findings(
            findings,
            lim["findings"],
            ["id", "severity", "scope", "blocking", "title", "details", "recommendation"],
        ),
        "tests_summary": payload.get("tests_summary"),
        "tests_executed": pack_tests_executed(payload.get("tests_executed") or [], lim["tests_executed"]),
        "inputs": payload.get("inputs") or {},
        "stats": {
            "findings": len(findings),
        },
    }
    return packed


def build_prd_pack(
    payload: Dict[str, Any],
    *,
    source_path: Optional[str] = None,
    limits: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    env_limits = core._env_limits().get("prd") or {}
    lim = {**core.PRD_LIMITS, **env_limits, **(limits or {})}
    findings = payload.get("findings") or []
    action_items = truncate_list(payload.get("action_items") or [], lim["action_items"])

    packed = {
        "schema": core.SCHEMA,
        "pack_version": core.PACK_VERSION,
        "type": "prd",
        "kind": "review",
        "ticket": payload.get("ticket"),
        "slug": payload.get("slug"),
        "generated_at": payload.get("generated_at"),
        "status": payload.get("status"),
        "recommended_status": payload.get("recommended_status"),
        "source_path": source_path,
        "findings": pack_findings(findings, lim["findings"], ["id", "severity", "title", "details"]),
        "action_items": action_items,
        "stats": {
            "findings": len(findings),
            "action_items": len(payload.get("action_items") or []),
        },
    }
    return packed


def build_rlm_pack(
    nodes: List[Dict[str, Any]],
    links: List[Dict[str, Any]],
    *,
    ticket: Optional[str],
    slug_hint: Optional[str] = None,
    source_path: Optional[str] = None,
    limits: Optional[Dict[str, int]] = None,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    env_limits = core._env_limits().get("rlm") or {}
    lim = {**core.RLM_LIMITS, **env_limits, **(limits or {})}

    file_nodes = [node for node in nodes if node.get("node_kind") == "file"]
    link_counts: Dict[str, int] = {}
    for link in links:
        if link.get("unverified"):
            continue
        src = str(link.get("src_file_id") or "")
        dst = str(link.get("dst_file_id") or "")
        if src:
            link_counts[src] = link_counts.get(src, 0) + 1
        if dst:
            link_counts[dst] = link_counts.get(dst, 0) + 1

    keyword_hits: set[str] = set()
    if root and ticket:
        targets_path = root / "reports" / "research" / f"{ticket}-rlm-targets.json"
        if targets_path.exists():
            try:
                targets_payload = json.loads(targets_path.read_text(encoding="utf-8"))
            except Exception:
                targets_payload = {}
            for raw_path in targets_payload.get("keyword_hits") or []:
                path_text = str(raw_path).strip()
                if not path_text:
                    continue
                keyword_hits.add(file_id_for_path(Path(path_text)))

    def by_link_count(node: Dict[str, Any]) -> tuple:
        file_id = str(node.get("file_id") or node.get("id") or "")
        boost = 1 if file_id and file_id in keyword_hits else 0
        return (-(link_counts.get(file_id, 0) + boost), str(node.get("path") or ""))

    entry_roles = {"web", "controller", "job", "config", "infra"}
    exclude_roles = {"model", "dto"}

    def _roles(node: Dict[str, Any]) -> set[str]:
        return {str(role) for role in (node.get("framework_roles") or []) if str(role)}

    entrypoints = [
        node for node in file_nodes if (_roles(node) & entry_roles) and not (_roles(node) & exclude_roles)
    ]
    entrypoints = sorted(entrypoints, key=by_link_count)

    hotspots = sorted(file_nodes, key=by_link_count)

    integration_roles = {"service", "repo", "config", "infra"}
    integration_points = [
        node
        for node in file_nodes
        if (_roles(node) & integration_roles) and not (_roles(node) & exclude_roles)
    ]
    integration_points = sorted(integration_points, key=by_link_count)

    test_hooks = [node for node in file_nodes if node.get("test_hooks")]
    test_hooks = sorted(test_hooks, key=by_link_count)

    risks = [node for node in file_nodes if node.get("risks")]
    risks = sorted(risks, key=by_link_count)

    recommended = []
    seen: set[str] = set()
    for group in (entrypoints, hotspots, integration_points):
        for node in group:
            file_id = str(node.get("file_id") or node.get("id") or "")
            if not file_id or file_id in seen:
                continue
            seen.add(file_id)
            recommended.append(node)
            if len(recommended) >= lim["recommended_reads"]:
                break
        if len(recommended) >= lim["recommended_reads"]:
            break

    links_total = len(links)
    verified_links = [link for link in links if not link.get("unverified")]
    links_unverified = links_total - len(verified_links)
    links_sample = pack_rlm_links(
        verified_links,
        limit=lim["links"],
        root=root,
        snippet_chars=lim["evidence_snippet_chars"],
    )
    link_stats = load_rlm_links_stats(root, ticket) if root and ticket else None
    link_warnings = rlm_link_warnings(link_stats) if link_stats else []
    unverified_warn_ratio: Optional[float] = None
    if root:
        settings = load_rlm_settings(root)
        raw_unverified_ratio = settings.get("link_unverified_warn_ratio")
        try:
            unverified_value = float(raw_unverified_ratio)
        except (TypeError, ValueError):
            unverified_value = None
        if unverified_value is not None and 0 < unverified_value <= 1:
            unverified_warn_ratio = unverified_value
    if unverified_warn_ratio and links_total:
        ratio = links_unverified / links_total
        if ratio >= unverified_warn_ratio:
            link_warnings.append(
                "rlm unverified links ratio high: "
                f"unverified={links_unverified} total={links_total} ratio={ratio:.2f}"
            )

    worklist_status, worklist_entries, _ = load_rlm_worklist_summary(root, ticket)
    if worklist_status == "ready" and worklist_entries == 0:
        pack_status = "ready"
    elif worklist_status:
        pack_status = "pending"
    else:
        pack_status = "ready"

    packed = {
        "schema": core.SCHEMA,
        "pack_version": core.PACK_VERSION,
        "type": "rlm",
        "kind": "pack",
        "ticket": ticket,
        "slug": slug_hint or ticket,
        "slug_hint": slug_hint,
        "generated_at": core._utc_timestamp(),
        "status": pack_status,
        "source_path": source_path,
        "stats": {
            "nodes": len(file_nodes),
            "nodes_total": len(file_nodes),
            "links": links_total,
            "links_unverified": links_unverified,
            "links_included": len(links_sample),
        },
        "entrypoints": pack_rlm_nodes(entrypoints, lim["entrypoints"]),
        "hotspots": pack_rlm_nodes(hotspots, lim["hotspots"]),
        "integration_points": pack_rlm_nodes(integration_points, lim["integration_points"]),
        "test_hooks": pack_rlm_nodes(test_hooks, lim["test_hooks"]),
        "risks": pack_rlm_nodes(risks, lim["risks"]),
        "recommended_reads": pack_rlm_nodes(recommended, lim["recommended_reads"]),
        "links": links_sample,
    }
    if link_stats:
        packed["stats"]["link_search"] = {
            "links_truncated": bool(link_stats.get("links_truncated")),
            "symbols_total": int(link_stats.get("symbols_total") or 0),
            "symbols_scanned": int(link_stats.get("symbols_scanned") or 0),
            "symbols_truncated": int(link_stats.get("symbols_truncated") or 0),
            "candidate_truncated": int(link_stats.get("candidate_truncated") or 0),
            "rg_calls": int(link_stats.get("rg_calls") or 0),
            "rg_timeouts": int(link_stats.get("rg_timeouts") or 0),
            "rg_errors": int(link_stats.get("rg_errors") or 0),
        }
    warnings = list(link_warnings)
    if worklist_status is not None:
        packed["stats"]["worklist_status"] = worklist_status
    if worklist_entries is not None:
        packed["stats"]["worklist_entries"] = worklist_entries
        if worklist_entries > 0:
            warnings.append(f"rlm worklist pending: entries={worklist_entries}")
            nodes_total = len(file_nodes)
            threshold = max(1, int(worklist_entries * 0.5))
            if nodes_total < threshold:
                warnings.append(
                    f"rlm pack partial: nodes_total={nodes_total} worklist_entries={worklist_entries}"
                )
    if warnings:
        packed["warnings"] = warnings
    return packed

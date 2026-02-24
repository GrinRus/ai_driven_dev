#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "node_modules",
    "dist",
    "build",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".jar"}

RUNTIME_REF_RE = re.compile(
    r"(?:\$\{CLAUDE_PLUGIN_ROOT\}/)?(skills/[A-Za-z0-9_.-]+/runtime/[A-Za-z0-9_./-]+\.py)"
)
SKILL_RUNTIME_CALL_RE = re.compile(
    r"(?:python3\s+)?(?:\"|')?\$\{CLAUDE_PLUGIN_ROOT\}/(skills/[A-Za-z0-9_.-]+/runtime/[A-Za-z0-9_./-]+\.py)"
)
SUBAGENT_RE = re.compile(r"subagent `feature-dev-aidd:([a-z0-9-]+)`", re.IGNORECASE)
FEATURE_SKILL_RE = re.compile(r"^feature-dev-aidd:([a-z0-9-]+)$", re.IGNORECASE)
WITH_NAME_CORE_RE = re.compile(
    r"with_name\((?:\"|')([A-Za-z0-9_.-]+)(?:\"|')\)\s*/\s*(?:\"|')([A-Za-z0-9_.-]+)(?:\"|')"
)
STATUS_DRAFT_RE = re.compile(r"^(?:Status|Статус):\s*Draft\b", re.IGNORECASE | re.MULTILINE)
RUNTIME_PATH_MENTION_RE = re.compile(r"(skills/[A-Za-z0-9_.-]+/runtime/[A-Za-z0-9_.-]+\.py)")
BACKLOG_TASK_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s*(.*)$")
DOC_PATH_RE = re.compile(r"(docs/[A-Za-z0-9_.\-/]+\.md)")

ROOT_DOC_FILES = {
    "README.md",
    "README.en.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "backlog.md",
    "aidd_test_flow_prompt_ralph_script.txt",
    "aidd_test_flow_prompt_ralph_script_full.txt",
}

REACHABILITY_EDGE_TYPES = {
    "command_subagent",
    "agent_preload_skill",
    "skill_runtime_ref",
    "runtime_import",
    "runtime_dynamic_load",
}


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _normalize_rel(value: str) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def _parse_bool(value: Any) -> bool:
    norm = str(value or "").strip().lower()
    return norm in {"1", "true", "yes", "on"}


def parse_frontmatter(text: str) -> Dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data: Dict[str, Any] = {}
    current_list_key: Optional[str] = None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("-"):
            if current_list_key is None:
                continue
            current = data.get(current_list_key)
            if not isinstance(current, list):
                current = []
                data[current_list_key] = current
            item = stripped.lstrip("-").strip().strip('"').strip("'")
            if item:
                current.append(item)
            continue
        current_list_key = None
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not value:
            data[key] = []
            current_list_key = key
        else:
            data[key] = value
    return data


def _extract_doc_refs_from_line(text: str) -> Set[str]:
    refs: Set[str] = set()
    for backtick in re.findall(r"`([^`]+)`", text):
        normalized = _normalize_rel(backtick)
        if normalized.startswith("docs/") and normalized.endswith(".md"):
            refs.add(normalized)
        for match in DOC_PATH_RE.findall(normalized):
            refs.add(_normalize_rel(match))
    for match in DOC_PATH_RE.findall(text):
        refs.add(_normalize_rel(match))
    return refs


def _open_backlog_doc_refs(backlog_text: str) -> Set[str]:
    if not backlog_text:
        return set()
    refs: Set[str] = set()
    in_open_task = False
    for raw in backlog_text.splitlines():
        task_match = BACKLOG_TASK_RE.match(raw)
        if task_match:
            in_open_task = task_match.group(1) == " "
            if in_open_task:
                refs.update(_extract_doc_refs_from_line(task_match.group(2)))
            continue
        if re.match(r"^\s*-\s*\[[ xX]\]", raw):
            in_open_task = False
            continue
        if in_open_task:
            refs.update(_extract_doc_refs_from_line(raw))
    return refs


def _should_skip_file(path: Path) -> bool:
    if any(part in EXCLUDED_DIRS for part in path.parts):
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    return False


def _iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _should_skip_file(path):
            continue
        yield path


def _iter_text_files(root: Path) -> Iterable[Path]:
    for path in _iter_files(root):
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        yield path


def _source_kind(rel_path: str) -> str:
    if rel_path.startswith("tests/"):
        return "test"
    if rel_path.startswith("hooks/") and rel_path.endswith(".sh"):
        return "hook_sh"
    if rel_path.startswith("docs/") or rel_path in ROOT_DOC_FILES or rel_path.startswith("dev/"):
        return "doc"
    return "other"


def _runtime_module_name(rel_path: str) -> str:
    parts = Path(rel_path).parts
    if len(parts) < 4:
        return ""
    tail = list(parts[3:])  # after skills/<name>/runtime/
    if not tail:
        return ""
    last = tail[-1]
    if last == "__init__.py":
        tail = tail[:-1]
    else:
        tail[-1] = last[:-3] if last.endswith(".py") else last
    if not tail:
        return "aidd_runtime"
    return "aidd_runtime." + ".".join(tail)


def _extract_import_modules(source: str) -> Set[str]:
    modules: Set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return modules

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "aidd_runtime" or name.startswith("aidd_runtime."):
                    modules.add(name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            mod = node.module or ""
            if mod == "aidd_runtime":
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    modules.add(f"aidd_runtime.{alias.name}")
            elif mod.startswith("aidd_runtime"):
                modules.add(mod)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    modules.add(f"{mod}.{alias.name}")
    return modules


def _extract_dynamic_runtime_targets(source: str, rel_path: str, root: Path) -> Set[str]:
    src = root / rel_path
    targets: Set[str] = set()
    for match in WITH_NAME_CORE_RE.finditer(source):
        dir_name = match.group(1)
        file_name = match.group(2)
        candidate = src.parent / dir_name / file_name
        if candidate.exists():
            targets.add(candidate.relative_to(root).as_posix())
    return targets


def _parse_seed_templates(init_path: Path) -> List[str]:
    text = _read_text(init_path)
    if not text:
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        if "SKILL_TEMPLATE_SEEDS" not in names:
            continue
        try:
            payload = ast.literal_eval(node.value)
        except Exception:
            return []
        templates: List[str] = []
        for row in payload:
            if not isinstance(row, (list, tuple)) or len(row) != 2:
                continue
            source_rel = _normalize_rel(str(row[0]))
            templates.append(source_rel)
        return sorted(set(templates))
    return []


def _load_plugin_registry(root: Path) -> Dict[str, Any]:
    plugin_path = root / ".claude-plugin" / "plugin.json"
    if not plugin_path.exists():
        return {"agents": [], "skills": []}
    try:
        payload = json.loads(plugin_path.read_text(encoding="utf-8"))
    except Exception:
        return {"agents": [], "skills": []}
    agents = payload.get("agents") or []
    skills = payload.get("skills") or []
    if isinstance(agents, str):
        agents = [agents]
    if isinstance(skills, str):
        skills = [skills]
    return {
        "agents": [_normalize_rel(item) for item in agents if str(item).strip()],
        "skills": [_normalize_rel(item) for item in skills if str(item).strip()],
    }


def _skill_name_to_node_id(skill_name: str, skill_infos: Mapping[str, Dict[str, Any]]) -> str:
    info = skill_infos.get(skill_name)
    if info:
        return str(info["node_id"])
    return f"shared_skill:{skill_name}"


def _build_revision_payload(root: Path, *, generated_at: Optional[str] = None) -> Dict[str, Any]:
    plugin = _load_plugin_registry(root)
    runtime_files = sorted(path.relative_to(root).as_posix() for path in root.glob("skills/*/runtime/**/*.py"))
    runtime_set = set(runtime_files)

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    node_paths: Dict[str, str] = {}

    def add_node(node_id: str, node_type: str, **attrs: Any) -> None:
        existing = nodes.get(node_id)
        if existing is None:
            payload = {"id": node_id, "type": node_type}
            payload.update(attrs)
            nodes[node_id] = payload
            path = payload.get("path")
            if isinstance(path, str) and path:
                node_paths[node_id] = path
            return
        if existing.get("type") != node_type:
            existing["type"] = existing.get("type", node_type)
        for key, value in attrs.items():
            if value in (None, "", []):
                continue
            existing[key] = value
            if key == "path" and isinstance(value, str):
                node_paths[node_id] = value

    def add_edge(edge_type: str, source: str, target: str, **attrs: Any) -> None:
        payload: Dict[str, Any] = {"type": edge_type, "source": source, "target": target}
        if attrs:
            payload["meta"] = dict(sorted(attrs.items()))
        edges.append(payload)

    def ensure_runtime_node(rel_path: str) -> str:
        rel = _normalize_rel(rel_path)
        node_id = f"runtime_py:{rel}"
        add_node(node_id, "runtime_py", path=rel, exists=1 if rel in runtime_set else 0)
        return node_id

    # Runtime nodes first.
    for rel in runtime_files:
        ensure_runtime_node(rel)

    # Skill nodes + edges to runtime + subagents + templates.
    skill_infos: Dict[str, Dict[str, Any]] = {}
    skill_docs = sorted(root.glob("skills/*/SKILL.md"))
    for skill_path in skill_docs:
        rel = skill_path.relative_to(root).as_posix()
        text = _read_text(skill_path)
        fm = parse_frontmatter(text)
        skill_name = str(fm.get("name") or skill_path.parent.name).strip() or skill_path.parent.name
        user_invocable = _parse_bool(fm.get("user-invocable"))
        node_type = "command_skill" if user_invocable else "shared_skill"
        node_id = f"{node_type}:{skill_name}"
        add_node(
            node_id,
            node_type,
            path=rel,
            name=skill_name,
            user_invocable=1 if user_invocable else 0,
        )
        runtimes = sorted(set(_normalize_rel(m.group(1)) for m in SKILL_RUNTIME_CALL_RE.finditer(text)))
        subagents = sorted(set(SUBAGENT_RE.findall(text)))
        template_files = sorted(
            path.relative_to(root).as_posix() for path in skill_path.parent.glob("templates/*") if path.is_file()
        )
        for runtime_rel in runtimes:
            runtime_id = ensure_runtime_node(runtime_rel)
            add_edge("skill_runtime_ref", node_id, runtime_id)
        for agent_name in subagents:
            agent_id = f"agent:{agent_name}"
            add_node(agent_id, "agent", name=agent_name)
            add_edge("command_subagent", node_id, agent_id)
        for template_rel in template_files:
            template_id = f"template:{template_rel}"
            add_node(template_id, "template", path=template_rel)
            add_edge("skill_template_ref", node_id, template_id)

        skill_infos[skill_name] = {
            "name": skill_name,
            "path": rel,
            "user_invocable": user_invocable,
            "node_id": node_id,
            "runtimes": runtimes,
            "subagents": subagents,
            "templates": template_files,
            "is_shared": not user_invocable,
        }

    # Agent nodes + preload edges.
    agent_infos: Dict[str, Dict[str, Any]] = {}
    for agent_path in sorted(root.glob("agents/*.md")):
        rel = agent_path.relative_to(root).as_posix()
        text = _read_text(agent_path)
        fm = parse_frontmatter(text)
        agent_name = str(fm.get("name") or agent_path.stem).strip() or agent_path.stem
        agent_id = f"agent:{agent_name}"
        add_node(agent_id, "agent", path=rel, name=agent_name)
        raw_skills = fm.get("skills") or []
        preload_refs: List[str] = []
        if isinstance(raw_skills, list):
            preload_refs = [str(item).strip() for item in raw_skills if str(item).strip()]
        preload_skills: List[str] = []
        for item in preload_refs:
            match = FEATURE_SKILL_RE.match(item)
            if not match:
                continue
            skill_name = match.group(1)
            preload_skills.append(skill_name)
            target_id = _skill_name_to_node_id(skill_name, skill_infos)
            if target_id not in nodes:
                add_node(target_id, "shared_skill", name=skill_name)
            add_edge("agent_preload_skill", agent_id, target_id)
        agent_infos[agent_name] = {
            "name": agent_name,
            "path": rel,
            "preload_skills": sorted(set(preload_skills)),
            "node_id": agent_id,
        }

    # Hooks wiring + hook scripts.
    hook_scripts = sorted(path.relative_to(root).as_posix() for path in root.glob("hooks/*.sh"))
    for rel in hook_scripts:
        add_node(f"hook_sh:{rel}", "hook_sh", path=rel)
    hooks_json_path = root / "hooks" / "hooks.json"
    if hooks_json_path.exists():
        hooks_payload = json.loads(_read_text(hooks_json_path) or "{}")
        hooks_map = hooks_payload.get("hooks") or {}
        if isinstance(hooks_map, dict):
            for event_name, entries in sorted(hooks_map.items()):
                event_id = f"doc:hooks/hooks.json#{event_name}"
                add_node(event_id, "doc", path=f"hooks/hooks.json#{event_name}", doc_kind="hook_event")
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    for hook in entry.get("hooks") or []:
                        if not isinstance(hook, dict):
                            continue
                        command = str(hook.get("command") or "")
                        for match in re.finditer(r"\$\{CLAUDE_PLUGIN_ROOT\}/(hooks/[A-Za-z0-9_.-]+\.sh)", command):
                            hook_rel = _normalize_rel(match.group(1))
                            hook_id = f"hook_sh:{hook_rel}"
                            add_node(hook_id, "hook_sh", path=hook_rel)
                            add_edge("hook_event_to_hook", event_id, hook_id, event=event_name)

    # Init seed map -> templates.
    init_rel = "skills/aidd-init/runtime/init.py"
    init_seed_source_id = f"doc:{init_rel}#SKILL_TEMPLATE_SEEDS"
    add_node(init_seed_source_id, "doc", path=f"{init_rel}#SKILL_TEMPLATE_SEEDS", doc_kind="seed_map")
    for template_rel in _parse_seed_templates(root / init_rel):
        template_id = f"template:{template_rel}"
        add_node(template_id, "template", path=template_rel)
        add_edge("init_seed_template", init_seed_source_id, template_id)

    # Runtime import graph through aidd_runtime namespace.
    module_index: Dict[str, List[str]] = defaultdict(list)
    for rel in runtime_files:
        module_name = _runtime_module_name(rel)
        if module_name:
            module_index[module_name].append(rel)
    for rel in runtime_files:
        source_text = _read_text(root / rel)
        source_id = f"runtime_py:{rel}"
        imported_modules = sorted(_extract_import_modules(source_text))
        for module_name in imported_modules:
            targets = module_index.get(module_name) or []
            for target_rel in sorted(set(targets)):
                target_id = ensure_runtime_node(target_rel)
                add_edge("runtime_import", source_id, target_id, module=module_name)
        dynamic_targets = sorted(_extract_dynamic_runtime_targets(source_text, rel, root))
        for target_rel in dynamic_targets:
            target_id = ensure_runtime_node(target_rel)
            add_edge("runtime_dynamic_load", source_id, target_id)

    # Text references from hooks/doc/test -> runtime.
    text_files = list(_iter_text_files(root))
    file_text_cache = {path.relative_to(root).as_posix(): _read_text(path) for path in text_files}
    open_backlog_doc_refs = _open_backlog_doc_refs(file_text_cache.get("backlog.md", ""))
    for source_rel, text in sorted(file_text_cache.items()):
        source_kind = _source_kind(source_rel)
        if source_kind not in {"hook_sh", "doc", "test"}:
            continue
        if source_kind == "hook_sh":
            source_id = f"hook_sh:{source_rel}"
            add_node(source_id, "hook_sh", path=source_rel)
            edge_type = "hook_ref_runtime"
        else:
            source_id = f"doc:{source_rel}"
            add_node(source_id, "doc", path=source_rel, doc_kind=source_kind)
            edge_type = f"{source_kind}_ref_runtime"
        runtime_refs = sorted(set(_normalize_rel(match.group(1)) for match in RUNTIME_REF_RE.finditer(text)))
        for runtime_rel in runtime_refs:
            runtime_id = ensure_runtime_node(runtime_rel)
            add_edge(edge_type, source_id, runtime_id)

    # Reachability from user-invocable command skills.
    adjacency: Dict[str, Set[str]] = defaultdict(set)
    for edge in edges:
        if edge["type"] in REACHABILITY_EDGE_TYPES:
            adjacency[str(edge["source"])].add(str(edge["target"]))
    command_node_ids = sorted(
        info["node_id"] for info in skill_infos.values() if bool(info.get("user_invocable"))
    )
    reachable: Set[str] = set()
    queue: deque[str] = deque(command_node_ids)
    while queue:
        node_id = queue.popleft()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        for target in sorted(adjacency.get(node_id, set())):
            if target not in reachable:
                queue.append(target)

    # Incoming references by path for triage.
    incoming_by_path: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        target = str(edge["target"])
        target_path = node_paths.get(target)
        if not target_path:
            continue
        source = str(edge["source"])
        source_node = nodes.get(source, {})
        incoming_by_path[target_path].append(
            {
                "edge_type": edge["type"],
                "source_id": source,
                "source_type": source_node.get("type", ""),
                "source_path": source_node.get("path", ""),
                "source_doc_kind": source_node.get("doc_kind", ""),
            }
        )

    # Path mention index for conservative safe detection.
    all_repo_files = sorted(path.relative_to(root).as_posix() for path in _iter_files(root))
    mention_index: Dict[str, Set[str]] = {rel: set() for rel in all_repo_files}
    for target_rel in all_repo_files:
        for source_rel, text in file_text_cache.items():
            if source_rel == target_rel:
                continue
            if target_rel in text:
                mention_index.setdefault(target_rel, set()).add(source_rel)

    # Unused triage: safe (conservative) + candidates.
    safe_items: List[Dict[str, Any]] = []
    protected_paths: Set[str] = set(plugin["agents"])
    for entry in plugin["skills"]:
        rel = _normalize_rel(entry)
        skill_dir = root / rel
        if skill_dir.is_dir():
            for file_path in skill_dir.rglob("*"):
                if file_path.is_file():
                    protected_paths.add(file_path.relative_to(root).as_posix())
    protected_paths.update(runtime_files)
    protected_paths.update(hook_scripts)
    protected_paths.update(path.relative_to(root).as_posix() for path in root.glob("skills/*/templates/*") if path.is_file())
    protected_paths.update(path.relative_to(root).as_posix() for path in root.glob("skills/*/CONTRACT.yaml"))
    protected_paths.update(path.relative_to(root).as_posix() for path in root.glob("skills/aidd-core/runtime/schemas/**/*") if path.is_file())

    for rel in sorted(all_repo_files):
        if not (rel.startswith("docs/") or rel.startswith("dev/") or rel in ROOT_DOC_FILES):
            continue
        if rel in protected_paths:
            continue
        if rel.startswith("tests/"):
            continue
        incoming = incoming_by_path.get(rel, [])
        mentions = sorted(mention_index.get(rel, set()))
        if incoming or mentions:
            continue
        safe_items.append(
            {
                "path": rel,
                "reason": "no inbound references in graph or textual mentions",
                "confidence": "high",
                "risk": "low",
                "proposed_action": "delete",
                "required_checks": [
                    "tests/repo_tools/ci-lint.sh",
                    "tests/repo_tools/smoke-workflow.sh",
                ],
            }
        )

    candidates: List[Dict[str, Any]] = []

    # Candidate 1: detached agents (registry exists, not reachable from user command chain).
    plugin_agent_names: Dict[str, str] = {}
    for rel in plugin["agents"]:
        name = Path(rel).stem
        text = _read_text(root / rel)
        fm = parse_frontmatter(text)
        front_name = str(fm.get("name") or name).strip() or name
        plugin_agent_names[front_name] = rel
    for agent_name, rel in sorted(plugin_agent_names.items()):
        node_id = f"agent:{agent_name}"
        if node_id in reachable:
            continue
        candidates.append(
            {
                "path": rel,
                "kind": "graph_detached_agent",
                "reason": "agent is present in plugin registry but unreachable from user-invocable stage chain",
                "confidence": "high",
                "risk": "medium",
                "proposed_action": "archive",
                "required_checks": [
                    "python3 tests/repo_tools/lint-prompts.py --root .",
                    "tests/repo_tools/ci-lint.sh",
                ],
            }
        )

    # Candidate 2: draft docs referencing missing runtime paths.
    for doc_path in sorted(root.glob("docs/**/*.md")):
        rel = doc_path.relative_to(root).as_posix()
        text = _read_text(doc_path)
        if not STATUS_DRAFT_RE.search(text):
            continue
        mentions = sorted(set(_normalize_rel(match.group(1)) for match in RUNTIME_PATH_MENTION_RE.finditer(text)))
        missing = [item for item in mentions if not (root / item).exists()]
        if not missing:
            continue
        if rel in open_backlog_doc_refs:
            continue
        candidates.append(
            {
                "path": rel,
                "kind": "draft_doc_missing_runtime_paths",
                "reason": "draft document contains runtime paths that do not exist in repository",
                "confidence": "high",
                "risk": "low",
                "proposed_action": "archive",
                "required_checks": [
                    "confirm roadmap ownership and whether doc must remain discoverable",
                    "tests/repo_tools/ci-lint.sh",
                ],
                "missing_runtime_paths": missing,
            }
        )

    # Deduplicate candidates by path+kind and deterministic order.
    dedup_candidates: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for item in candidates:
        key = (str(item.get("path", "")), str(item.get("kind", "")))
        if key not in dedup_candidates:
            dedup_candidates[key] = item
    candidates = [dedup_candidates[key] for key in sorted(dedup_candidates)]

    actions: List[Dict[str, Any]] = []
    order = 1
    for item in safe_items:
        actions.append(
            {
                "order": order,
                "target": item["path"],
                "proposed_action": item["proposed_action"],
                "reason": item["reason"],
                "risk": item["risk"],
                "required_checks": item["required_checks"],
            }
        )
        order += 1
    for item in candidates:
        actions.append(
            {
                "order": order,
                "target": item["path"],
                "proposed_action": item["proposed_action"],
                "reason": item["reason"],
                "risk": item["risk"],
                "required_checks": item["required_checks"],
            }
        )
        order += 1

    cleanup_plan = {
        "policy": "conservative_no_autodelete",
        "summary": "No immediate destructive cleanup; all entries require validation before merge.",
        "actions": actions,
        "validation_commands": [
            "python3 tests/repo_tools/repo_topology_audit.py --repo-root . --output-json dev/reports/revision/repo-revision.graph.json --output-md dev/reports/revision/repo-revision.md --output-cleanup dev/reports/revision/repo-cleanup-plan.json",
            "tests/repo_tools/ci-lint.sh",
            "tests/repo_tools/smoke-workflow.sh",
        ],
    }

    command_names = sorted(name for name, info in skill_infos.items() if bool(info.get("user_invocable")))
    detached_agent_names = sorted(
        item["path"] for item in candidates if item.get("kind") == "graph_detached_agent"
    )
    edge_counter = Counter(edge["type"] for edge in edges)
    node_counter = Counter(node.get("type", "") for node in nodes.values())

    metrics = {
        "command_skill_count": len(command_names),
        "shared_skill_count": int(node_counter.get("shared_skill", 0)),
        "agent_count": int(node_counter.get("agent", 0)),
        "runtime_count": int(node_counter.get("runtime_py", 0)),
        "hook_count": int(node_counter.get("hook_sh", 0)),
        "template_count": int(node_counter.get("template", 0)),
        "doc_count": int(node_counter.get("doc", 0)),
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "reachable_node_count": len(reachable),
        "reachable_runtime_count": len([node for node in reachable if node.startswith("runtime_py:")]),
        "detached_agent_paths": detached_agent_names,
        "edge_types": dict(sorted(edge_counter.items())),
    }

    payload = {
        "schema": "aidd.repo_revision.v1",
        "meta": {
            "generated_at": generated_at or _utc_timestamp(),
            "repo_root": root.as_posix(),
            "sources": {
                "plugin_registry": ".claude-plugin/plugin.json",
                "skills_glob": "skills/*/SKILL.md",
                "agents_glob": "agents/*.md",
                "runtime_glob": "skills/*/runtime/**/*.py",
                "hooks_wiring": "hooks/hooks.json",
                "template_seed_map": "skills/aidd-init/runtime/init.py:SKILL_TEMPLATE_SEEDS",
            },
        },
        "nodes": sorted(nodes.values(), key=lambda item: (str(item.get("type", "")), str(item.get("id", "")))),
        "edges": sorted(
            edges,
            key=lambda item: (
                str(item.get("type", "")),
                str(item.get("source", "")),
                str(item.get("target", "")),
                json.dumps(item.get("meta", {}), sort_keys=True),
            ),
        ),
        "metrics": metrics,
        "unused": {
            "safe": sorted(safe_items, key=lambda item: str(item.get("path", ""))),
            "candidates": candidates,
        },
        "cleanup_plan": cleanup_plan,
        "command_chains": _build_command_chains(skill_infos, agent_infos, edges, reachable),
        "shared_skill_coverage": _build_shared_skill_coverage(skill_infos, agent_infos),
    }
    return payload


def _build_command_chains(
    skill_infos: Mapping[str, Dict[str, Any]],
    agent_infos: Mapping[str, Dict[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    reachable: Set[str],
) -> List[Dict[str, Any]]:
    edges_by_source: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for edge in edges:
        edges_by_source[str(edge["source"])].append(edge)

    chains: List[Dict[str, Any]] = []
    for skill_name, info in sorted(skill_infos.items()):
        if not bool(info.get("user_invocable")):
            continue
        command_node = str(info["node_id"])
        subagents = sorted(info.get("subagents", []))
        agent_rows = []
        for agent_name in subagents:
            agent_info = agent_infos.get(agent_name, {})
            agent_rows.append(
                {
                    "name": agent_name,
                    "path": agent_info.get("path", ""),
                    "preload_skills": sorted(agent_info.get("preload_skills", [])),
                }
            )
        runtime_refs = sorted(info.get("runtimes", []))
        chains.append(
            {
                "command": skill_name,
                "skill_path": info.get("path", ""),
                "runtime_refs": runtime_refs,
                "subagents": subagents,
                "agent_preloads": agent_rows,
                "templates": sorted(info.get("templates", [])),
                "reachable": 1 if command_node in reachable else 0,
                "edge_count": len(edges_by_source.get(command_node, [])),
            }
        )
    return chains


def _build_shared_skill_coverage(
    skill_infos: Mapping[str, Dict[str, Any]],
    agent_infos: Mapping[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    shared_skills = sorted(name for name, info in skill_infos.items() if bool(info.get("is_shared")))
    for skill_name in shared_skills:
        skill_info = skill_infos[skill_name]
        preloaded_by = sorted(
            agent_name
            for agent_name, agent_info in agent_infos.items()
            if skill_name in set(agent_info.get("preload_skills", []))
        )
        referenced_by_commands = sorted(
            command_name
            for command_name, command_info in skill_infos.items()
            if bool(command_info.get("user_invocable"))
            and any(
                runtime_ref.startswith(f"skills/{skill_name}/runtime/")
                for runtime_ref in command_info.get("runtimes", [])
            )
        )
        rows.append(
            {
                "shared_skill": skill_name,
                "skill_path": skill_info.get("path", ""),
                "runtime_count": len(skill_info.get("runtimes", [])),
                "preloaded_by_agents": preloaded_by,
                "direct_command_runtime_refs": referenced_by_commands,
            }
        )
    return rows


def _render_markdown(payload: Mapping[str, Any]) -> str:
    meta = payload.get("meta") or {}
    metrics = payload.get("metrics") or {}
    command_chains = payload.get("command_chains") or []
    shared_coverage = payload.get("shared_skill_coverage") or []
    unused = payload.get("unused") or {}
    safe = unused.get("safe") or []
    candidates = unused.get("candidates") or []
    cleanup = payload.get("cleanup_plan") or {}

    lines: List[str] = []
    lines.append("# Repository Revision Report")
    lines.append("")
    lines.append(f"schema: `{payload.get('schema', '')}`")
    lines.append(f"generated_at: `{meta.get('generated_at', '')}`")
    lines.append("")
    lines.append("## Executive summary")
    lines.append("")
    lines.append(f"- Total nodes: **{metrics.get('total_nodes', 0)}**")
    lines.append(f"- Total edges: **{metrics.get('total_edges', 0)}**")
    lines.append(f"- User-invocable commands: **{metrics.get('command_skill_count', 0)}**")
    lines.append(f"- Reachable runtimes from command chain: **{metrics.get('reachable_runtime_count', 0)}**")
    lines.append(f"- Detached agents: **{len(metrics.get('detached_agent_paths', []))}**")
    lines.append("")
    lines.append("Key findings:")
    if not candidates:
        lines.append("- No candidate findings from current graph/triage run.")
    else:
        kind_counts = Counter(str(item.get("kind", "unknown")) for item in candidates)
        kind_summary = ", ".join(f"`{kind}`={count}" for kind, count in sorted(kind_counts.items()))
        lines.append(f"- Candidate count: **{len(candidates)}** ({kind_summary})")
        for item in candidates:
            lines.append(
                f"- `{item.get('path', '')}` (`{item.get('kind', '')}`): {item.get('reason', '')}"
            )
    unreachable_commands = sorted(
        str(row.get("command", "")) for row in command_chains if not bool(row.get("reachable"))
    )
    if unreachable_commands:
        lines.append(
            "- Unreachable command skills from root traversal: "
            + ", ".join(f"`{name}`" for name in unreachable_commands)
        )
    detached_paths = metrics.get("detached_agent_paths", [])
    if detached_paths:
        lines.append("- Detached agents: " + ", ".join(f"`{path}`" for path in detached_paths))
    lines.append("")

    lines.append("## Topology matrix")
    lines.append("")
    for row in command_chains:
        lines.append(f"### `/feature-dev-aidd:{row.get('command', '')}`")
        lines.append(f"- Skill: `{row.get('skill_path', '')}`")
        lines.append(f"- Runtime refs: {len(row.get('runtime_refs', []))}")
        for runtime_ref in row.get("runtime_refs", []):
            lines.append(f"  - `{runtime_ref}`")
        subagents = row.get("subagents", [])
        if subagents:
            lines.append(f"- Subagents: {', '.join(f'`{item}`' for item in subagents)}")
            for agent in row.get("agent_preloads", []):
                preload = agent.get("preload_skills", [])
                lines.append(
                    f"  - `{agent.get('name', '')}` preloads: "
                    + (", ".join(f"`{item}`" for item in preload) if preload else "none")
                )
        else:
            lines.append("- Subagents: none")
        templates = row.get("templates", [])
        if templates:
            lines.append("- Templates:")
            for template in templates:
                lines.append(f"  - `{template}`")
        else:
            lines.append("- Templates: none")
        lines.append(f"- Reachable from root chain: `{bool(row.get('reachable'))}`")
        lines.append("")

    lines.append("## Shared skills coverage")
    lines.append("")
    for row in shared_coverage:
        lines.append(f"### `{row.get('shared_skill', '')}`")
        lines.append(f"- Skill path: `{row.get('skill_path', '')}`")
        preloaded = row.get("preloaded_by_agents", [])
        direct = row.get("direct_command_runtime_refs", [])
        lines.append("- Preloaded by agents: " + (", ".join(f"`{item}`" for item in preloaded) if preloaded else "none"))
        lines.append(
            "- Direct command runtime refs: "
            + (", ".join(f"`{item}`" for item in direct) if direct else "none")
        )
        lines.append("")

    lines.append("## Unused triage")
    lines.append("")
    lines.append("### Safe-to-delete")
    lines.append("")
    if not safe:
        lines.append("- none")
    else:
        for item in safe:
            lines.append(
                f"- `{item.get('path', '')}`: action=`{item.get('proposed_action', '')}`, "
                f"confidence=`{item.get('confidence', '')}`, risk=`{item.get('risk', '')}`"
            )
            lines.append(f"  - reason: {item.get('reason', '')}")
    lines.append("")

    lines.append("### Candidates")
    lines.append("")
    if not candidates:
        lines.append("- none")
    else:
        for item in candidates:
            lines.append(
                f"- `{item.get('path', '')}` (`{item.get('kind', '')}`): action=`{item.get('proposed_action', '')}`, "
                f"confidence=`{item.get('confidence', '')}`, risk=`{item.get('risk', '')}`"
            )
            lines.append(f"  - reason: {item.get('reason', '')}")
            checks = item.get("required_checks", [])
            if checks:
                lines.append("  - required_checks:")
                for check in checks:
                    lines.append(f"    - {check}")
    lines.append("")

    lines.append("## Cleanup plan")
    lines.append("")
    cleanup_actions = cleanup.get("actions", [])
    if not cleanup_actions:
        lines.append("- none")
    else:
        for action in cleanup_actions:
            lines.append(
                f"{action.get('order', '')}. `{action.get('target', '')}` -> `{action.get('proposed_action', '')}` "
                f"(risk: `{action.get('risk', '')}`)"
            )
            lines.append(f"   - reason: {action.get('reason', '')}")
    lines.append("")
    lines.append("Validation commands:")
    for cmd in cleanup.get("validation_commands", []):
        lines.append(f"- `{cmd}`")
    lines.append("")

    lines.append("## Appendix")
    lines.append("")
    lines.append("- Sources of truth:")
    sources = (meta.get("sources") or {}) if isinstance(meta.get("sources"), Mapping) else {}
    for key, value in sorted(sources.items()):
        lines.append(f"  - `{key}`: `{value}`")
    edge_types = metrics.get("edge_types", {})
    if isinstance(edge_types, Mapping):
        lines.append("- Edge types:")
        for edge_type, count in sorted(edge_types.items()):
            lines.append(f"  - `{edge_type}`: {count}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_revision_payload(repo_root: Path, *, generated_at: Optional[str] = None) -> Dict[str, Any]:
    return _build_revision_payload(repo_root.resolve(), generated_at=generated_at)


def _format_output_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate repository topology graph + unused triage + cleanup plan.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    parser.add_argument(
        "--output-json",
        default="dev/reports/revision/repo-revision.graph.json",
        help="Output JSON graph path.",
    )
    parser.add_argument(
        "--output-md",
        default="dev/reports/revision/repo-revision.md",
        help="Output markdown report path.",
    )
    parser.add_argument(
        "--output-cleanup",
        default="dev/reports/revision/repo-cleanup-plan.json",
        help="Output cleanup-plan JSON path.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    root = Path(args.repo_root).resolve()
    payload = build_revision_payload(root)

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_cleanup = Path(args.output_cleanup)

    if not output_json.is_absolute():
        output_json = root / output_json
    if not output_md.is_absolute():
        output_md = root / output_md
    if not output_cleanup.is_absolute():
        output_cleanup = root / output_cleanup

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_cleanup.parent.mkdir(parents=True, exist_ok=True)

    output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    cleanup_payload = payload.get("cleanup_plan", {})
    output_cleanup.write_text(
        json.dumps(cleanup_payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output_md.write_text(_render_markdown(payload), encoding="utf-8")

    print(f"[repo-topology-audit] JSON: {_format_output_path(output_json, root)}")
    print(f"[repo-topology-audit] MD: {_format_output_path(output_md, root)}")
    print(f"[repo-topology-audit] CLEANUP: {_format_output_path(output_cleanup, root)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

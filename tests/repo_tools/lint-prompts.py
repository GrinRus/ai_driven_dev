#!/usr/bin/env python3
"""Validate Claude prompt and skill files."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

PROMPT_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
STATUS_RE = re.compile(r"(?:Status|Статус):\s*([A-Za-z-]+)")
ALLOWED_STATUSES = {"ready", "blocked", "pending", "warn", "reviewed", "draft"}
VALID_LANGS = {"ru", "en"}

TOOL_PATH_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/tools/[A-Za-z0-9_.-]+\.sh")
HOOK_PATH_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/hooks/[A-Za-z0-9_.-]+\.sh")
UNSCOPED_PLUGIN_PATH_RE = re.compile(r"(?<!\$\{CLAUDE_PLUGIN_ROOT\}/)(?:tools|hooks)/[A-Za-z0-9_.-]+\.sh")
TOOL_CLAUDE_WORKFLOW_RE = re.compile(r"\bclaude-workflow\b", re.IGNORECASE)
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
BASH_TOOL_RE = re.compile(r"^Bash\((.*)\)$")

SOFT_SKILL_LINES = 220
MAX_SKILL_LINES = 300
PRELOADED_SIZE_LIMIT_BYTES = 64 * 1024
ALLOWED_SUPPORT_DIRS = {"scripts", "runtime", "examples", "assets", "templates", "references"}
REQUIRED_CONTRACT_FIELDS = [
    "when to run:",
    "inputs:",
    "outputs:",
    "failure mode:",
    "next action:",
]
RESEARCHER_STAGE_FORBIDDEN_RLM_TOOLS = (
    "rlm_nodes_build.py",
    "rlm_verify.py",
    "rlm_links_build.py",
    "rlm_jsonl_compact.py",
    "reports_pack.py",
)

STAGE_SKILLS = [
    "aidd-init",
    "idea-new",
    "researcher",
    "plan-new",
    "review-spec",
    "spec-interview",
    "tasks-new",
    "implement",
    "review",
    "qa",
    "status",
]

STAGE_PYTHON_ENTRYPOINTS = {
    "aidd-init": "skills/aidd-init/runtime/init.py",
    "idea-new": "skills/idea-new/runtime/analyst_check.py",
    "researcher": "skills/researcher/runtime/research.py",
    "plan-new": "skills/plan-new/runtime/research_check.py",
    "review-spec": "skills/review-spec/runtime/prd_review_cli.py",
    "spec-interview": "skills/spec-interview/runtime/spec_interview.py",
    "tasks-new": "skills/tasks-new/runtime/tasks_new.py",
    "implement": "skills/implement/runtime/implement_run.py",
    "review": "skills/review/runtime/review_run.py",
    "qa": "skills/qa/runtime/qa_run.py",
    "status": "skills/status/runtime/status.py",
}
STAGE_CANONICAL_BODY_RUNTIME_ENV_REQUIRED = {
    "idea-new",
    "researcher",
    "plan-new",
    "review-spec",
    "spec-interview",
    "tasks-new",
    "status",
}

LOOP_STAGES = {"implement", "review", "qa", "status"}
NO_FORK_STAGE_SUBAGENT_COUNTS: Dict[str, int] = {
    "idea-new": 1,
    "tasks-new": 1,
    "implement": 1,
    "review": 1,
    "qa": 1,
}
NO_FORK_FORBIDDEN_PHRASES = (
    "forked context",
    "(fork)",
    "delegate to subagent",
)
LEGACY_STAGE_ALIAS_TO_CANONICAL = {
    "/feature-dev-aidd:planner": "/feature-dev-aidd:plan-new",
    "/feature-dev-aidd:tasklist-refiner": "/feature-dev-aidd:tasks-new",
    "/feature-dev-aidd:implementer": "/feature-dev-aidd:implement",
    "/feature-dev-aidd:reviewer": "/feature-dev-aidd:review",
}
LOOP_MANUAL_PREFLIGHT_BAN_RE = re.compile(
    r"(?:(?:не\s+запуск|запрещено|do not run|forbidden).{0,220}preflight_prepare\.py"
    r"|preflight_prepare\.py.{0,220}(?:запрещено|forbidden|do not run|не\s+запуск))",
    re.IGNORECASE | re.DOTALL,
)
LOOP_MANUAL_STAGE_RESULT_BAN_RE = re.compile(
    r"(?:(?:не\s+пис|не\s+создав|запрещено|do not (?:write|create)|forbidden).{0,260}"
    r"stage\.[a-z0-9_.-]*result\.json"
    r"|stage\.[a-z0-9_.-]*result\.json.{0,260}(?:запрещено|forbidden|do not (?:write|create)|не\s+пис|не\s+создав))",
    re.IGNORECASE | re.DOTALL,
)
LOOP_WRAPPER_CHAIN_RE = re.compile(
    r"(?:wrapper chain|wrapper-?only|slash stage command|canonical stage chain).{0,260}"
    r"(?:actions_apply\.py|postflight|stage_result\.py)",
    re.IGNORECASE | re.DOTALL,
)
STAGE_BODY_REL_RUNTIME_RE = re.compile(
    r"python3\s+(?:\./)?skills/[A-Za-z0-9_.-]+/runtime/[A-Za-z0-9_.-]+\.py",
    re.IGNORECASE,
)
LOOP_STAGE_FORBIDDEN_ALLOWED_TOOL_SNIPPETS = (
    "skills/aidd-loop/runtime/preflight_prepare.py",
    "skills/aidd-flow-state/runtime/stage_result.py",
)
PRELOADED_SKILLS = {
    "aidd-core",
    "aidd-docio",
    "aidd-flow-state",
    "aidd-observability",
    "aidd-loop",
    "aidd-rlm",
    "aidd-policy",
    "aidd-stage-research",
}
SHARED_STAGE_SCRIPT_OWNERS = {
    "aidd-core",
    "aidd-loop",
    "aidd-rlm",
    "aidd-policy",
    "aidd-docio",
    "aidd-flow-state",
    "aidd-observability",
}
AGENT_REQUIRED_SHARED_SKILLS = {"feature-dev-aidd:aidd-core", "feature-dev-aidd:aidd-policy"}
AGENT_REQUIRED_LOOP_SKILLS = {"feature-dev-aidd:aidd-loop"}
AGENT_REQUIRED_RLM_SKILL = "feature-dev-aidd:aidd-rlm"
AGENT_REQUIRED_STAGE_RESEARCH_SKILL = "feature-dev-aidd:aidd-stage-research"
AGENT_LOOP_PRELOAD_ROLES = {"implementer", "reviewer", "qa"}
AGENT_RLM_PRELOAD_ROLES = {
    "analyst",
    "planner",
    "plan-reviewer",
    "prd-reviewer",
    "researcher",
    "reviewer",
    "spec-interview-writer",
    "tasklist-refiner",
    "validator",
}
# role -> skill refs allowed outside matrix requirements.
AGENT_PRELOAD_WAIVERS: Dict[str, set[str]] = {}
SKILL_RUNTIME_TOOL_RE = re.compile(
    r"(?:python3\s+)?\$\{CLAUDE_PLUGIN_ROOT\}/skills/([^/]+)/runtime/([A-Za-z0-9_.-]+\.py)"
)

FORBIDDEN_AGENT_STAGE_TOOL_MAP = {
    "${CLAUDE_PLUGIN_ROOT}/tools/analyst-check.sh": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/idea-new/runtime/analyst_check.py",
    "${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/plan-new/runtime/research_check.py",
    "${CLAUDE_PLUGIN_ROOT}/tools/prd-review.sh": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-spec/runtime/prd_review_cli.py",
    "${CLAUDE_PLUGIN_ROOT}/tools/reports-pack.sh": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/reports_pack.py",
    "${CLAUDE_PLUGIN_ROOT}/tools/rlm-nodes-build.sh": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_nodes_build.py",
    "${CLAUDE_PLUGIN_ROOT}/tools/rlm-verify.sh": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_verify.py",
    "${CLAUDE_PLUGIN_ROOT}/tools/rlm-links-build.sh": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_links_build.py",
    "${CLAUDE_PLUGIN_ROOT}/tools/rlm-jsonl-compact.sh": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_jsonl_compact.py",
    "${CLAUDE_PLUGIN_ROOT}/tools/rlm-finalize.sh": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_finalize.py",
    "${CLAUDE_PLUGIN_ROOT}/tools/qa.sh": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/qa.py",
    "${CLAUDE_PLUGIN_ROOT}/tools/status.sh": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/status/runtime/status.py",
    "${CLAUDE_PLUGIN_ROOT}/tools/index-sync.sh": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/status/runtime/index_sync.py",
}

AGENT_REQUIRED_SECTIONS = [
    "Контекст",
    "Входные артефакты",
    "Автоматизация",
    "Пошаговый план",
    "Fail-fast и вопросы",
    "Формат ответа",
]

OUTPUT_CONTRACT_FIELDS = {
    "skills/aidd-policy/SKILL.md": [
        "Status:",
        "Work item key:",
        "Artifacts updated:",
        "Tests:",
        "Blockers/Handoff:",
        "Next actions:",
        "AIDD:READ_LOG:",
        "AIDD:ACTIONS_LOG:",
    ]
}

INDEX_SCHEMA_PATH = Path("skills/aidd-core/templates/index.schema.json")
INDEX_REQUIRED_FIELDS = [
    "schema",
    "ticket",
    "slug",
    "stage",
    "updated",
    "summary",
    "artifacts",
    "reports",
    "next3",
    "open_questions",
    "risks_top5",
    "checks",
]

POLICY_DOC = Path("docs/skill-language.md")
BASELINE_JSON_PRIMARY = Path("aidd/reports/migrations/commands_to_skills_frontmatter.json")
BASELINE_JSON_FALLBACK = Path("dev/reports/migrations/commands_to_skills_frontmatter.json")
LEGACY_BASH_POLICY_ENV = "AIDD_BASH_LEGACY_POLICY"
LEGACY_BASH_POLICIES = {"allow", "warn", "error"}


@dataclass
class PromptFile:
    path: Path
    kind: str  # "agent" or "skill"
    lang: str
    front_matter: Dict[str, str | list[str]]
    sections: List[str]
    body: str
    line_count: int

    @property
    def stem(self) -> str:  # pragma: no cover - trivial
        return self.path.stem


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Claude prompt and skill files")
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parents[2],
        type=Path,
        help="Workflow root containing agents/skills",
    )
    return parser.parse_args()


def _resolve_aidd_root(root: Path) -> Path:
    template_root = root / "templates" / "aidd"
    if template_root.is_dir():
        return template_root
    candidate = root / "aidd"
    if candidate.is_dir():
        return candidate
    return root


def _extract_section(body: str, title: str) -> str | None:
    title_token = f"## {title}".lower()
    lines = body.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip().lower() == title_token:
            start = idx + 1
            break
    if start is None:
        return None
    section_lines: List[str] = []
    for line in lines[start:]:
        if line.strip().startswith("## "):
            break
        section_lines.append(line)
    content = "\n".join(section_lines).strip()
    return content or None


def read_prompt(path: Path, kind: str, expected_lang: str) -> Tuple[PromptFile | None, List[str]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    errors: List[str] = []
    if not lines or lines[0].strip() != "---":
        errors.append(f"{path}: missing YAML front matter (start with ---)")
        return None, errors

    closing = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing = idx
            break
    if closing is None:
        errors.append(f"{path}: missing closing --- for front matter")
        return None, errors

    front_lines = lines[1:closing]
    front: Dict[str, str | list[str]] = {}
    current_list_key: str | None = None
    for idx, raw in enumerate(front_lines, start=2):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("-"):
            if not current_list_key or not isinstance(front.get(current_list_key), list):
                errors.append(f"{path}:{idx}: unexpected list item without a list key")
                continue
            item = stripped.lstrip("-").strip().strip('"').strip("'")
            if item:
                front[current_list_key].append(item)
            continue
        current_list_key = None
        if ":" not in stripped:
            errors.append(f"{path}:{idx}: invalid front matter line (expected key: value)")
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        if key in front:
            errors.append(f"{path}:{idx}: duplicate front matter key `{key}`")
            continue
        clean_value = value.strip().strip('"').strip("'")
        if clean_value == "":
            front[key] = []
            current_list_key = key
        else:
            front[key] = clean_value

    body_lines = lines[closing + 1 :]
    body = "\n".join(body_lines)
    sections: List[str] = []
    for raw in body_lines:
        striped = raw.strip()
        if striped.startswith("## "):
            sections.append(striped[3:].strip())

    lang_value = front.get("lang", "")
    lang = lang_value.strip() if isinstance(lang_value, str) else ""
    if lang and lang not in VALID_LANGS:
        errors.append(f"{path}: unsupported lang `{lang}` (expected one of {sorted(VALID_LANGS)})")
    if expected_lang and lang and lang != expected_lang:
        errors.append(f"{path}: lang `{lang}` does not match expected `{expected_lang}`")

    return (
        PromptFile(
            path=path,
            kind=kind,
            lang=lang or expected_lang,
            front_matter=front,
            sections=sections,
            body=body,
            line_count=len(lines),
        ),
        errors,
    )


def ensure_keys(info: PromptFile, keys: Iterable[str]) -> List[str]:
    errors = []
    front = info.front_matter
    for key in keys:
        if key not in front:
            errors.append(f"{info.path}: missing `{key}` in front matter")
    return errors


def ensure_sections(info: PromptFile, required: List[str]) -> List[str]:
    errors = []
    sections = info.sections
    current_index = -1
    for section in required:
        try:
            idx = sections.index(section)
        except ValueError:
            errors.append(f"{info.path}: missing section `## {section}`")
            continue
        if idx <= current_index:
            errors.append(
                f"{info.path}: section `## {section}` out of order (expected after previous sections)"
            )
        current_index = idx
    return errors


def _as_string(value: str | list[str] | None) -> str:
    if isinstance(value, list):
        return ""
    return value or ""


def _as_list(value: str | list[str] | None) -> List[str]:
    if isinstance(value, list):
        return [item.strip() for item in value if item.strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _normalize_tool_list(value: str | list[str] | None) -> List[str]:
    items = _as_list(value)
    cleaned: List[str] = []
    for item in items:
        text = item.strip().strip('"').strip("'")
        if text:
            cleaned.append(text)
    return cleaned


def _parse_bash_tool(entry: str) -> tuple[str | None, str | None]:
    if not entry.startswith("Bash("):
        return None, None
    match = BASH_TOOL_RE.match(entry.strip())
    if not match:
        return None, None
    inner = match.group(1).strip()
    if inner.endswith(":*"):
        return inner[:-2].strip(), "legacy"
    if inner.endswith(" *"):
        return inner[:-2].strip(), "modern"
    return inner.strip(), None


def _legacy_bash_policy() -> str:
    raw = os.getenv(LEGACY_BASH_POLICY_ENV, "error").strip().lower()
    if raw in LEGACY_BASH_POLICIES:
        return raw
    return "error"


def validate_bash_tool_grammar(info: PromptFile) -> tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    key = "allowed-tools" if info.kind == "skill" else "tools" if info.kind == "agent" else ""
    if not key:
        return errors, warnings
    policy = _legacy_bash_policy()
    for entry in _normalize_tool_list(info.front_matter.get(key)):
        if not entry.startswith("Bash("):
            continue
        command, style = _parse_bash_tool(entry)
        if command is None:
            errors.append(
                f"{info.path}: invalid Bash tool syntax `{entry}`; expected `Bash(<command> *)`."
            )
            continue
        if style is None:
            errors.append(
                f"{info.path}: invalid Bash wildcard syntax `{entry}`; "
                "supported forms are `Bash(<command> *)` and transitional colon-wildcard syntax."
            )
            continue
        if style == "legacy":
            message = (
                f"{info.path}: legacy Bash wildcard syntax is deprecated (`{entry}`); "
                "use `Bash(<command> *)`."
            )
            if policy == "warn":
                warnings.append(message)
            elif policy == "error":
                errors.append(
                    message.replace("is deprecated", "is forbidden by policy")
                )
    return errors, warnings


def validate_statuses(info: PromptFile) -> List[str]:
    errors: List[str] = []
    for match in STATUS_RE.finditer(info.body):
        status = match.group(1).strip().lower()
        if status and status not in ALLOWED_STATUSES:
            errors.append(f"{info.path}: unknown status `{status}` in body (allowed: {sorted(ALLOWED_STATUSES)})")
    return errors


def validate_placeholders(info: PromptFile) -> List[str]:
    if "&lt;ticket&gt;" in info.body:
        return [f"{info.path}: replace HTML escape `&lt;ticket&gt;` with `<ticket>`"]
    return []


def validate_checkbox_guidance(info: PromptFile) -> List[str]:
    errors: List[str] = []
    for line in info.body.splitlines():
        lower = line.lower()
        if "checkbox updated" in lower and ("заканч" in lower or "в конце" in lower):
            errors.append(f"{info.path}: `Checkbox updated` should be the first line, not last")
    return errors


def _iter_tool_scan_lines(info: PromptFile) -> Iterable[str]:
    lines = info.body.splitlines()
    in_fence = False
    skip_examples = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith("## "):
            skip_examples = stripped.lower() == "## примеры cli"
        if skip_examples:
            continue
        yield re.sub(r"\[[^\]]+\]\([^)]+\)", "", line)


def validate_tool_mentions(info: PromptFile) -> List[str]:
    errors: List[str] = []
    tool_mentions: set[str] = set()
    has_claude_workflow = False
    for line in _iter_tool_scan_lines(info):
        tool_mentions.update(match.group(0) for match in TOOL_PATH_RE.finditer(line))
        tool_mentions.update(match.group(0) for match in HOOK_PATH_RE.finditer(line))
        if TOOL_CLAUDE_WORKFLOW_RE.search(line):
            has_claude_workflow = True

    if not tool_mentions and not has_claude_workflow:
        return []

    if info.kind == "skill":
        allowed_tools = set(_normalize_tool_list(info.front_matter.get("allowed-tools")))
    elif info.kind == "agent":
        allowed_tools = set(_normalize_tool_list(info.front_matter.get("tools")))
    else:
        allowed_tools = set()
    allowed_bash = [item for item in allowed_tools if item.startswith("Bash(")]

    if has_claude_workflow and not allowed_bash:
        errors.append(f"{info.path}: mentions claude-workflow without Bash in allowed-tools")

    for mention in sorted(tool_mentions):
        if not any(mention in tool for tool in allowed_tools if tool.startswith("Bash(")):
            errors.append(f"{info.path}: tool `{mention}` mentioned but not in allowed-tools")
    return errors


def validate_plugin_asset_mentions(info: PromptFile, root: Path) -> List[str]:
    errors: List[str] = []
    mentions: set[str] = set()
    for line in _iter_tool_scan_lines(info):
        mentions.update(match.group(0) for match in TOOL_PATH_RE.finditer(line))
        mentions.update(match.group(0) for match in HOOK_PATH_RE.finditer(line))
        if "${CLAUDE_PLUGIN_ROOT}/../" in line:
            errors.append(f"{info.path}: plugin asset path uses `../` ({line.strip()})")
        for match in UNSCOPED_PLUGIN_PATH_RE.finditer(line):
            errors.append(f"{info.path}: plugin asset path must use ${{CLAUDE_PLUGIN_ROOT}} ({match.group(0)})")

    for mention in sorted(mentions):
        rel = mention.split("${CLAUDE_PLUGIN_ROOT}/", 1)[1]
        if not (root / rel).exists():
            errors.append(f"{info.path}: referenced plugin asset missing: {rel}")

    return errors


def validate_required_write_tools(info: PromptFile) -> List[str]:
    if info.kind != "agent":
        return []
    if info.stem not in {"implementer", "tasklist-refiner"}:
        return []
    tools = _normalize_tool_list(info.front_matter.get("tools"))
    missing = [name for name in ("Read", "Write", "Edit") if name not in tools]
    if missing:
        return [f"{info.path}: missing required tools {missing}"]
    return []


def _skill_ref_to_name(raw: str) -> str:
    value = raw.strip()
    if ":" in value:
        value = value.rsplit(":", 1)[-1]
    return value.strip()


def validate_agent_skill_refs(info: PromptFile, root: Path) -> List[str]:
    errors: List[str] = []
    skills = _normalize_tool_list(info.front_matter.get("skills"))
    for skill_ref in skills:
        skill_name = _skill_ref_to_name(skill_ref)
        if not skill_name:
            errors.append(f"{info.path}: invalid empty skill ref `{skill_ref}`")
            continue
        skill_path = root / "skills" / skill_name / "SKILL.md"
        if not skill_path.exists():
            errors.append(f"{info.path}: missing preload skill `{skill_ref}` -> {skill_path}")
    return errors


def validate_agent_tool_policy(info: PromptFile) -> List[str]:
    errors: List[str] = []
    tools = _normalize_tool_list(info.front_matter.get("tools"))
    for entry in tools:
        if "${CLAUDE_PLUGIN_ROOT}/skills/" in entry and "/scripts/" in entry:
            errors.append(
                f"{info.path}: agents must not call stage/shared wrappers directly ({entry})"
            )
        for fallback_path, canonical_path in FORBIDDEN_AGENT_STAGE_TOOL_MAP.items():
            if fallback_path in entry:
                errors.append(
                    f"{info.path}: agent tools must use `{canonical_path}` instead of fallback wrapper `{fallback_path}`"
                )
    has_rlm_tooling = any(
        "rlm_" in entry or "reports_pack.py" in entry or "rlm_slice.py" in entry
        for entry in tools
        if entry.startswith("Bash(")
    )
    if has_rlm_tooling:
        skills = _normalize_tool_list(info.front_matter.get("skills"))
        if AGENT_REQUIRED_RLM_SKILL not in skills:
            errors.append(
                f"{info.path}: RLM tools require preload skill `{AGENT_REQUIRED_RLM_SKILL}`"
            )
    return errors


def validate_output_contract(info: PromptFile, root: Path) -> List[str]:
    rel_path = _relative_prompt_path(info, root)
    required_fields = OUTPUT_CONTRACT_FIELDS.get(rel_path)
    if not required_fields:
        return []
    errors: List[str] = []
    missing = [field for field in required_fields if field not in info.body]
    if missing:
        errors.append(f"{info.path}: output contract missing fields {missing}")
    return errors


def _relative_prompt_path(info: PromptFile, root: Path) -> str:
    try:
        return info.path.relative_to(root).as_posix()
    except ValueError:
        return info.path.as_posix()


def lint_agents(root: Path) -> Tuple[List[str], List[str], Dict[str, PromptFile]]:
    errors: List[str] = []
    warnings: List[str] = []
    agents: Dict[str, PromptFile] = {}
    agents_dir = root / "agents"
    if not agents_dir.exists():
        return [f"{agents_dir}: agents directory is missing"], warnings, agents

    for path in sorted(agents_dir.glob("*.md")):
        info, load_errors = read_prompt(path, "agent", "ru")
        if load_errors:
            errors.extend(load_errors)
            continue
        if info is None:
            continue
        agents[info.stem] = info
        errors.extend(
            ensure_keys(
                info,
                [
                    "name",
                    "description",
                    "lang",
                    "prompt_version",
                    "source_version",
                    "tools",
                    "permissionMode",
                    "skills",
                ],
            )
        )
        errors.extend(ensure_sections(info, AGENT_REQUIRED_SECTIONS))
        errors.extend(validate_statuses(info))
        errors.extend(validate_placeholders(info))
        errors.extend(validate_checkbox_guidance(info))
        errors.extend(validate_tool_mentions(info))
        errors.extend(validate_plugin_asset_mentions(info, root))
        errors.extend(validate_required_write_tools(info))
        errors.extend(validate_agent_skill_refs(info, root))
        errors.extend(validate_agent_tool_policy(info))
        grammar_errors, grammar_warnings = validate_bash_tool_grammar(info)
        errors.extend(grammar_errors)
        warnings.extend(grammar_warnings)

        if "Output follows aidd-core skill" not in info.body:
            errors.append(f"{info.path}: missing anchor line 'Output follows aidd-core skill'")

        skills = _normalize_tool_list(info.front_matter.get("skills"))
        for required in AGENT_REQUIRED_SHARED_SKILLS:
            if required not in skills:
                errors.append(f"{info.path}: missing skill preload {required}")
        waivers = AGENT_PRELOAD_WAIVERS.get(info.stem, set())
        loop_required = info.stem in AGENT_LOOP_PRELOAD_ROLES
        if loop_required:
            for required in AGENT_REQUIRED_LOOP_SKILLS:
                if required not in skills:
                    errors.append(f"{info.path}: missing role-based preload {required}")
        else:
            for required in AGENT_REQUIRED_LOOP_SKILLS:
                if required in skills and required not in waivers:
                    errors.append(f"{info.path}: preload {required} is forbidden for role `{info.stem}`")

        rlm_required = info.stem in AGENT_RLM_PRELOAD_ROLES
        if rlm_required:
            if AGENT_REQUIRED_RLM_SKILL not in skills:
                errors.append(f"{info.path}: missing role-based preload {AGENT_REQUIRED_RLM_SKILL}")
        elif AGENT_REQUIRED_RLM_SKILL in skills and AGENT_REQUIRED_RLM_SKILL not in waivers:
            errors.append(f"{info.path}: preload {AGENT_REQUIRED_RLM_SKILL} is forbidden for role `{info.stem}`")
        if info.stem == "researcher" and AGENT_REQUIRED_STAGE_RESEARCH_SKILL not in skills:
            errors.append(f"{info.path}: missing role-based preload {AGENT_REQUIRED_STAGE_RESEARCH_SKILL}")

        version = _as_string(info.front_matter.get("prompt_version"))
        if version and not PROMPT_VERSION_RE.match(version):
            errors.append(f"{info.path}: prompt_version `{version}` must match X.Y.Z")
        source_version = _as_string(info.front_matter.get("source_version"))
        if source_version and not PROMPT_VERSION_RE.match(source_version):
            errors.append(f"{info.path}: source_version `{source_version}` must match X.Y.Z")

    return errors, warnings, agents


def lint_skills(root: Path) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    skills_root = root / "skills"
    if not skills_root.exists():
        return [f"{skills_root}: skills directory is missing"], warnings

    if not (root / POLICY_DOC).exists():
        errors.append(f"{root / POLICY_DOC}: missing skill language policy doc")

    baseline = None
    baseline_candidates = [
        root / BASELINE_JSON_PRIMARY,
        root / BASELINE_JSON_FALLBACK,
    ]
    baseline_path = next((path for path in baseline_candidates if path.exists()), baseline_candidates[0])
    if baseline_path.exists():
        try:
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{baseline_path}: invalid JSON ({exc})")
    else:
        tried = ", ".join(path.as_posix() for path in baseline_candidates)
        errors.append(f"{baseline_candidates[0]}: missing baseline for skills parity (tried: {tried})")

    baseline_rows = {row["stage"]: row for row in (baseline or {}).get("rows", [])}

    for path in sorted(skills_root.glob("*/SKILL.md")):
        info, load_errors = read_prompt(path, "skill", "")
        if load_errors:
            errors.extend(load_errors)
            continue
        if info is None:
            continue

        if info.line_count > MAX_SKILL_LINES:
            errors.append(f"{info.path}: exceeds max skill length ({info.line_count} > {MAX_SKILL_LINES} lines)")
        elif info.line_count > SOFT_SKILL_LINES:
            warnings.append(f"{info.path}: exceeds recommended skill length ({info.line_count} > {SOFT_SKILL_LINES} lines)")

        raw_text = path.read_text(encoding="utf-8")
        if CYRILLIC_RE.search(raw_text):
            errors.append(f"{info.path}: skills must be EN-only (Cyrillic detected)")

        errors.extend(validate_statuses(info))
        errors.extend(validate_placeholders(info))
        errors.extend(validate_tool_mentions(info))
        errors.extend(validate_plugin_asset_mentions(info, root))
        errors.extend(validate_output_contract(info, root))
        grammar_errors, grammar_warnings = validate_bash_tool_grammar(info)
        errors.extend(grammar_errors)
        warnings.extend(grammar_warnings)

        name = _as_string(info.front_matter.get("name"))
        if name and name != path.parent.name:
            errors.append(f"{info.path}: front matter name `{name}` does not match directory `{path.parent.name}`")

        lang = _as_string(info.front_matter.get("lang"))
        if lang and lang not in VALID_LANGS:
            errors.append(f"{info.path}: unsupported lang `{lang}`")

        model = _as_string(info.front_matter.get("model"))
        if model and model != "inherit":
            errors.append(f"{info.path}: model must be inherit")

        if path.parent.name in PRELOADED_SKILLS:
            errors.extend(
                ensure_keys(
                    info,
                    [
                        "description",
                        "lang",
                        "model",
                        "user-invocable",
                    ],
                )
            )

        user_invocable_raw = info.front_matter.get("user-invocable")
        user_invocable = _as_string(user_invocable_raw)
        if user_invocable_raw is None:
            errors.append(f"{info.path}: missing `user-invocable` in front matter")
        if path.parent.name in PRELOADED_SKILLS:
            if user_invocable != "false":
                errors.append(f"{info.path}: preloaded skills must be user-invocable: false")
        else:
            if user_invocable != "true":
                errors.append(f"{info.path}: stage skills must be user-invocable: true")

        disable_invocation = _as_string(info.front_matter.get("disable-model-invocation"))
        if path.parent.name in PRELOADED_SKILLS:
            if disable_invocation == "true":
                errors.append(f"{info.path}: preloaded skills must not set disable-model-invocation: true")
        elif path.parent.name == "status":
            if disable_invocation != "false":
                errors.append(f"{info.path}: status must set disable-model-invocation: false")
        else:
            if disable_invocation != "true":
                errors.append(f"{info.path}: stage skills must set disable-model-invocation: true")

        # stage skill requirements
        if path.parent.name in STAGE_SKILLS:
            errors.extend(
                ensure_keys(
                    info,
                    [
                        "description",
                        "argument-hint",
                        "lang",
                        "prompt_version",
                        "source_version",
                        "allowed-tools",
                        "model",
                    ],
                )
            )
            version = _as_string(info.front_matter.get("prompt_version"))
            if version and not PROMPT_VERSION_RE.match(version):
                errors.append(f"{info.path}: prompt_version `{version}` must match X.Y.Z")
            source_version = _as_string(info.front_matter.get("source_version"))
            if source_version and not PROMPT_VERSION_RE.match(source_version):
                errors.append(f"{info.path}: source_version `{source_version}` must match X.Y.Z")

            if "feature-dev-aidd:aidd-core" not in info.body:
                errors.append(f"{info.path}: missing reference to feature-dev-aidd:aidd-core")
            if path.parent.name in {"implement", "review", "qa"} and "feature-dev-aidd:aidd-loop" not in info.body:
                errors.append(f"{info.path}: missing reference to feature-dev-aidd:aidd-loop")

            for legacy_alias, canonical_alias in LEGACY_STAGE_ALIAS_TO_CANONICAL.items():
                if legacy_alias in info.body:
                    errors.append(
                        f"{info.path}: stage guidance uses legacy stage alias `{legacy_alias}`; "
                        f"use `{canonical_alias}`"
                    )

            if path.parent.name in {"implement", "review", "qa"}:
                body_lower = info.body.lower()
                if "actions_apply.py" not in body_lower:
                    errors.append(f"{info.path}: missing actions_apply.py reference")
                if "fill actions.json" not in body_lower:
                    errors.append(f"{info.path}: missing 'Fill actions.json' step")
                if not LOOP_MANUAL_PREFLIGHT_BAN_RE.search(info.body):
                    errors.append(
                        f"{info.path}: missing explicit policy that manual `preflight_prepare.py` invocation is forbidden"
                    )
                if not LOOP_MANUAL_STAGE_RESULT_BAN_RE.search(info.body):
                    errors.append(
                        f"{info.path}: missing explicit policy that manual `stage.*.result.json` write is forbidden"
                    )
                if not LOOP_WRAPPER_CHAIN_RE.search(info.body):
                    errors.append(
                        f"{info.path}: missing wrapper-only canonical chain guidance for loop stages"
                    )
            if (
                path.parent.name in STAGE_CANONICAL_BODY_RUNTIME_ENV_REQUIRED
                and STAGE_BODY_REL_RUNTIME_RE.search(info.body)
            ):
                errors.append(
                    f"{info.path}: stage guidance must use canonical runtime paths in body "
                    f"(`python3 ${{CLAUDE_PLUGIN_ROOT}}/skills/.../runtime/...`), not relative `python3 skills/...`"
                )

            context = _as_string(info.front_matter.get("context"))
            agent = _as_string(info.front_matter.get("agent"))
            skill_tools = _normalize_tool_list(info.front_matter.get("allowed-tools"))
            if path.parent.name in {"implement", "review", "qa"}:
                for forbidden_tool in LOOP_STAGE_FORBIDDEN_ALLOWED_TOOL_SNIPPETS:
                    if any(forbidden_tool in item for item in skill_tools):
                        errors.append(
                            f"{info.path}: loop stage allowed-tools must not include manual recovery surface "
                            f"`{forbidden_tool}`"
                        )

            python_entrypoint_rel = STAGE_PYTHON_ENTRYPOINTS[path.parent.name]
            python_entrypoint = root / python_entrypoint_rel
            if not python_entrypoint.exists():
                errors.append(f"{python_entrypoint}: missing canonical python entrypoint")
            python_tool_ref = f"python3 ${{CLAUDE_PLUGIN_ROOT}}/{python_entrypoint_rel}"
            if not any(python_tool_ref in item for item in skill_tools if item.startswith("Bash(")):
                errors.append(
                    f"{info.path}: allowed-tools must include canonical python entrypoint "
                    f"`Bash({python_tool_ref} *)`"
                )

            contracts = _extract_section(info.body, "Command contracts")
            if not contracts:
                errors.append(f"{info.path}: missing `## Command contracts` section")
            else:
                contracts_lc = contracts.lower()
                for marker in REQUIRED_CONTRACT_FIELDS:
                    if marker not in contracts_lc:
                        errors.append(f"{info.path}: command contracts missing `{marker}`")
                required_refs = [python_entrypoint_rel]
                if path.parent.name in {"implement", "review", "qa"}:
                    required_refs.append("actions_apply.py")
                for ref in required_refs:
                    if ref.lower() not in contracts_lc:
                        errors.append(f"{info.path}: command contracts missing critical command reference `{ref}`")
                if path.parent.name in {"implement", "review", "qa"}:
                    slash_ref = f"/feature-dev-aidd:{path.parent.name}"
                    slash_contract_heading = f"### `{slash_ref}"
                    if slash_contract_heading in contracts_lc:
                        errors.append(
                            f"{info.path}: command contracts must not duplicate self slash-stage entrypoint "
                            f"`{slash_ref}`; keep runtime contracts only"
                        )

            additional = _extract_section(info.body, "Additional resources")
            if not additional:
                errors.append(f"{info.path}: missing `## Additional resources` section")
            else:
                bullets = [line.strip() for line in additional.splitlines() if line.strip().startswith("-")]
                if not bullets:
                    errors.append(f"{info.path}: Additional resources must contain at least one bullet item")
                for bullet in bullets:
                    bullet_lc = bullet.lower()
                    if "when:" not in bullet_lc or "why:" not in bullet_lc:
                        errors.append(
                            f"{info.path}: Additional resources bullet must include `when:` and `why:` ({bullet})"
                        )

            for item in skill_tools:
                if not item.startswith("Bash("):
                    continue
                if "${CLAUDE_PLUGIN_ROOT}/skills/" in item and "/scripts/" in item:
                    errors.append(
                        f"{info.path}: stage skill must not reference legacy shell wrappers in allowed-tools ({item})"
                    )
                    continue
                runtime_match = SKILL_RUNTIME_TOOL_RE.search(item)
                if runtime_match:
                    owner = runtime_match.group(1)
                    if owner != path.parent.name and owner not in SHARED_STAGE_SCRIPT_OWNERS:
                        errors.append(
                            f"{info.path}: stage skill references foreign python entrypoint `{owner}` "
                            f"(allowed: own runtime + shared skills {sorted(SHARED_STAGE_SCRIPT_OWNERS)})"
                        )

            if path.parent.name == "researcher":
                forbidden_rlm_refs = [
                    item
                    for item in skill_tools
                    if "/skills/aidd-rlm/runtime/" in item
                    and any(token in item for token in RESEARCHER_STAGE_FORBIDDEN_RLM_TOOLS)
                ]
                if forbidden_rlm_refs:
                    errors.append(
                        f"{info.path}: researcher stage must not call shared RLM API directly in allowed-tools "
                        f"({forbidden_rlm_refs})"
                    )
                body_lc = info.body.lower()
                forbidden_in_steps = [
                    token for token in RESEARCHER_STAGE_FORBIDDEN_RLM_TOOLS if token in body_lc
                ]
                if forbidden_in_steps:
                    errors.append(
                        f"{info.path}: researcher stage steps must not depend on shared RLM internals "
                        f"({forbidden_in_steps}); use explicit handoff to aidd-rlm owner skill"
                    )
                subagent_mentions = len(re.findall(r"run subagent", info.body, flags=re.IGNORECASE))
                if subagent_mentions != 1:
                    errors.append(
                        f"{info.path}: researcher stage must contain exactly one `Run subagent` step "
                        f"(found {subagent_mentions})"
                    )
                body_lc = info.body.lower()
                forbidden_phrases = [
                    "forked context",
                    "(fork)",
                    "delegate to subagent",
                ]
                found_phrases = [phrase for phrase in forbidden_phrases if phrase in body_lc]
                if found_phrases:
                    errors.append(
                        f"{info.path}: researcher stage contains forbidden fork/delegation phrases "
                        f"{found_phrases}"
                    )

            if context:
                errors.append(
                    f"{info.path}: stage skills must not set `context`; use explicit `Run subagent` orchestration."
                )
            if agent:
                errors.append(
                    f"{info.path}: stage skills must not set `agent`; use explicit `Run subagent` orchestration."
                )

            expected_subagents = NO_FORK_STAGE_SUBAGENT_COUNTS.get(path.parent.name)
            if expected_subagents is not None:
                subagent_mentions = len(re.findall(r"run subagent", info.body, flags=re.IGNORECASE))
                if subagent_mentions != expected_subagents:
                    errors.append(
                        f"{info.path}: stage must contain exactly {expected_subagents} `Run subagent` step(s) "
                        f"(found {subagent_mentions})"
                    )
                body_lc = info.body.lower()
                forbidden_phrases = [phrase for phrase in NO_FORK_FORBIDDEN_PHRASES if phrase in body_lc]
                if forbidden_phrases:
                    errors.append(
                        f"{info.path}: stage contains forbidden fork/delegation phrases {forbidden_phrases}"
                    )

            # parity check against baseline
            row = baseline_rows.get(path.parent.name)
            if row:
                baseline_fm = row.get("frontmatter", {})
                forbidden_stage_tools = [
                    item for item in skill_tools if "${CLAUDE_PLUGIN_ROOT}/tools/" in item
                ]
                if forbidden_stage_tools:
                    errors.append(
                        f"{info.path}: stage skills must not use tools/* in allowed-tools "
                        f"({forbidden_stage_tools})"
                    )
                baseline_tools = list(baseline_fm.get("allowed-tools") or [])
                if skill_tools != baseline_tools:
                    errors.append(f"{info.path}: allowed-tools does not match baseline")
                for key in ("model", "prompt_version", "source_version", "lang", "argument-hint"):
                    current = _as_string(info.front_matter.get(key))
                    expected = baseline_fm.get(key)
                    if current != expected:
                        errors.append(f"{info.path}: `{key}` does not match baseline ({current!r} != {expected!r})")
            else:
                errors.append(f"{info.path}: missing baseline entry for stage {path.parent.name}")

    # required stage skills
    for stage in STAGE_SKILLS:
        path = skills_root / stage / "SKILL.md"
        if not path.exists():
            errors.append(f"{path}: missing stage skill")

    # support files policy:
    # - root-level supporting docs are allowed;
    # - examples/assets stay one level deep;
    # - runtime/scripts may contain nested executable resources.
    for skill_dir in sorted(skills_root.iterdir()):
        if not skill_dir.is_dir():
            continue
        for file in skill_dir.rglob("*"):
            if not file.is_file():
                continue
            if file.name == "SKILL.md":
                continue
            rel = file.relative_to(skill_dir)
            parts = rel.parts
            if len(parts) == 1:
                continue
            if parts[0] in {"runtime", "scripts"}:
                continue
            if len(parts) == 2 and parts[0] in ALLOWED_SUPPORT_DIRS:
                continue
            if len(parts) > 2:
                errors.append(
                    f"{file}: supporting files must be depth <= 1 (root-level or {sorted(ALLOWED_SUPPORT_DIRS)})"
                )
                continue
            if parts[0] not in ALLOWED_SUPPORT_DIRS:
                errors.append(
                    f"{file}: supporting files must be root-level or under {sorted(ALLOWED_SUPPORT_DIRS)}"
                )

    # preloaded size limit
    for skill in PRELOADED_SKILLS:
        skill_dir = skills_root / skill
        if not skill_dir.exists():
            errors.append(f"{skill_dir}: missing preloaded skill directory")
            continue
        total = 0
        for p in skill_dir.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(skill_dir)
            if rel.parts and rel.parts[0] in {"runtime", "scripts"}:
                # Executable/runtime files are not preloaded into prompt context.
                continue
            total += p.stat().st_size
        if total > PRELOADED_SIZE_LIMIT_BYTES:
            errors.append(
                f"{skill_dir}: preloaded skill size {total} exceeds limit {PRELOADED_SIZE_LIMIT_BYTES} bytes"
            )

    return errors, warnings


def validate_commands_relocated(root: Path) -> List[str]:
    commands_dir = root / "commands"
    if not commands_dir.exists():
        return []
    stage_files = [p for p in commands_dir.glob("*.md")]
    if stage_files:
        names = ", ".join(sorted(p.name for p in stage_files))
        return [f"{commands_dir}: stage entrypoints must not live in commands/ ({names})"]
    return []


def validate_template_artifacts(root: Path) -> List[str]:
    errors: List[str] = []
    critical = [
        "skills/aidd-core/templates/workspace-agents.md",
        "skills/aidd-core/templates/stage-lexicon.md",
        "skills/aidd-core/templates/index.schema.json",
        "skills/aidd-core/templates/context-pack.template.md",
        "skills/aidd-loop/templates/loop-pack.template.md",
        "skills/idea-new/templates/prd.template.md",
        "skills/plan-new/templates/plan.template.md",
        "skills/researcher/templates/research.template.md",
        "skills/spec-interview/templates/spec.template.yaml",
        "skills/tasks-new/templates/tasklist.template.md",
    ]
    for rel in critical:
        target = root / rel
        if not target.exists():
            errors.append(f"{target}: missing critical template artifact")
    return errors


def validate_plugin_manifest(root: Path, skills_expected: List[str], agents_expected: List[str]) -> List[str]:
    manifest_path = root / ".claude-plugin" / "plugin.json"
    if not manifest_path.exists():
        return [f"{manifest_path}: plugin manifest is missing"]
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{manifest_path}: invalid JSON ({exc})"]

    errors: List[str] = []

    def _normalize_entries(raw) -> List[str]:
        if raw is None:
            return []
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list):
            return []
        normalized = []
        for entry in raw:
            if not isinstance(entry, str):
                continue
            value = entry.strip()
            if value:
                normalized.append(value)
        return sorted(set(normalized))

    def _validate_list(key: str, expected: List[str]) -> List[str]:
        resolved_entries: List[str] = []
        raw = payload.get(key)
        entries = _normalize_entries(raw)
        if raw is None:
            errors.append(f"{manifest_path}: `{key}` is missing")
            return resolved_entries
        if entries:
            missing = [item for item in expected if item not in entries]
            extra = [item for item in entries if item not in expected]
            if missing:
                errors.append(f"{manifest_path}: {key} missing entries {missing}")
            if extra:
                errors.append(f"{manifest_path}: {key} has extra entries {extra}")
        for entry in entries:
            if not entry.startswith("./"):
                errors.append(f"{manifest_path}: `{key}` path must start with ./ ({entry})")
            if ".." in Path(entry).parts:
                errors.append(f"{manifest_path}: `{key}` path must not contain .. ({entry})")
            rel = entry[2:] if entry.startswith("./") else entry
            path = root / rel if rel else root
            if rel and not path.exists():
                errors.append(f"{manifest_path}: `{key}` path not found ({entry})")
                continue
            resolved_entries.append(entry)
        return resolved_entries

    def _normalize_rel(path: Path) -> str:
        return f"./{path.as_posix()}"

    skill_roots = _validate_list("skills", sorted({f"./skills/{Path(path).parent.name}" for path in skills_expected}))
    resolved_skills: List[str] = []
    for entry in skill_roots:
        rel = entry[2:] if entry.startswith("./") else entry
        path = root / rel
        if path.is_file():
            errors.append(f"{manifest_path}: `skills` entries must reference directories, not files ({entry})")
            continue
        if not path.is_dir():
            errors.append(f"{manifest_path}: `skills` entry must be a directory ({entry})")
            continue
        direct_skill = path / "SKILL.md"
        if direct_skill.is_file():
            resolved_skills.append(_normalize_rel(Path(rel) / "SKILL.md"))
            continue
        discovered = sorted(path.rglob("SKILL.md"))
        if not discovered:
            errors.append(f"{manifest_path}: `skills` directory has no SKILL.md ({entry})")
            continue
        resolved_skills.extend(_normalize_rel(skill.relative_to(root)) for skill in discovered)

    expected_skills = sorted(set(skills_expected))
    resolved_skills = sorted(set(resolved_skills))
    missing_skills = [item for item in expected_skills if item not in resolved_skills]
    extra_skills = [item for item in resolved_skills if item not in expected_skills]
    if missing_skills:
        errors.append(f"{manifest_path}: skills missing resolved entries {missing_skills}")
    if extra_skills:
        errors.append(f"{manifest_path}: skills has extra resolved entries {extra_skills}")

    _validate_list("agents", agents_expected)

    return errors


def validate_index_schema(root: Path) -> List[str]:
    errors: List[str] = []
    schema_path = root / INDEX_SCHEMA_PATH
    if not schema_path.exists():
        # Backward-compatible fallback for the previous source-of-truth layout.
        previous_aidd_root = _resolve_aidd_root(root)
        schema_path = previous_aidd_root / "docs" / "index" / "schema.json"
    if not schema_path.exists():
        errors.append(f"{schema_path}: missing index schema")
        return errors
    try:
        schema_payload = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{schema_path}: invalid JSON ({exc})")
        return errors
    required = schema_payload.get("required") or []
    missing = [field for field in INDEX_REQUIRED_FIELDS if field not in required]
    if missing:
        errors.append(f"{schema_path}: missing required fields {missing}")

    index_dir = schema_path.parent
    for path in sorted(index_dir.glob("*.json")):
        if path.name == schema_path.name:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path}: invalid JSON ({exc})")
            continue
        for field in INDEX_REQUIRED_FIELDS:
            if field not in payload:
                errors.append(f"{path}: missing field `{field}`")
    return errors


def main() -> int:
    args = parse_args()
    root = args.root
    if not root.exists():
        print(f"[prompt-lint] root {root} does not exist", file=sys.stderr)
        return 1

    errors: List[str] = []
    warnings: List[str] = []
    agent_errors, agent_warnings, agent_files = lint_agents(root)
    errors.extend(agent_errors)
    warnings.extend(agent_warnings)
    agent_ids = {info.front_matter.get("name", info.stem) for info in agent_files.values()}

    skill_errors, skill_warnings = lint_skills(root)
    errors.extend(skill_errors)
    warnings.extend(skill_warnings)
    errors.extend(validate_commands_relocated(root))
    errors.extend(validate_template_artifacts(root))

    skills_expected = sorted(
        f"./skills/{path.parent.name}/SKILL.md" for path in (root / "skills").glob("*/SKILL.md")
    )
    agents_expected = sorted(f"./agents/{path.name}" for path in (root / "agents").glob("*.md"))
    errors.extend(validate_plugin_manifest(root, skills_expected, agents_expected))
    errors.extend(validate_index_schema(root))

    for msg in warnings:
        print(f"[prompt-lint][warn] {msg}", file=sys.stderr)

    if errors:
        for msg in errors:
            print(f"[prompt-lint] {msg}", file=sys.stderr)
        return 1
    print("[prompt-lint] all prompts passed")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

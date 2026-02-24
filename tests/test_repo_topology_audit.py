from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_TOOL_PATH = REPO_ROOT / "tests" / "repo_tools" / "repo_topology_audit.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("repo_topology_audit", AUDIT_TOOL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {AUDIT_TOOL_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class RepoTopologyAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = _load_module()

    def _build_fixture_repo(self, root: Path) -> None:
        _write(
            root / ".claude-plugin" / "plugin.json",
            json.dumps(
                {
                    "name": "feature-dev-aidd",
                    "agents": [
                        "./agents/planner.md",
                        "./agents/validator.md",
                        "./agents/spec-interview-writer.md",
                    ],
                    "skills": [
                        "./skills/plan-new",
                        "./skills/spec-interview",
                        "./skills/qa",
                        "./skills/review",
                        "./skills/aidd-core",
                    ],
                },
                ensure_ascii=False,
            )
            + "\n",
        )

        _write(
            root / "skills" / "plan-new" / "SKILL.md",
            """---
name: plan-new
user-invocable: true
---

Run subagent `feature-dev-aidd:planner`, then run subagent `feature-dev-aidd:validator`.
Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/plan-new/runtime/research_check.py --ticket <ticket>`.
""",
        )
        _write(root / "skills" / "plan-new" / "runtime" / "research_check.py", "from aidd_runtime import runtime\n")

        _write(
            root / "skills" / "spec-interview" / "SKILL.md",
            """---
name: spec-interview
user-invocable: true
---

Run subagent `feature-dev-aidd:spec-interview-writer`.
Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/spec-interview/runtime/spec_interview.py --ticket <ticket>`.
""",
        )
        _write(root / "skills" / "spec-interview" / "runtime" / "spec_interview.py", "print('ok')\n")

        _write(
            root / "skills" / "qa" / "SKILL.md",
            """---
name: qa
user-invocable: true
---

Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/qa.py --ticket <ticket>`.
""",
        )
        _write(
            root / "skills" / "qa" / "runtime" / "qa.py",
            "from pathlib import Path\n"
            "_CORE_PATH = Path(__file__).resolve().with_name('qa_parts') / 'core.py'\n"
            "print(_CORE_PATH)\n",
        )
        _write(root / "skills" / "qa" / "runtime" / "qa_parts" / "__init__.py", "")
        _write(root / "skills" / "qa" / "runtime" / "qa_parts" / "core.py", "print('core')\n")

        _write(
            root / "skills" / "review" / "SKILL.md",
            """---
name: review
user-invocable: true
---

Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_run.py --ticket <ticket>`.
""",
        )
        _write(root / "skills" / "review" / "runtime" / "review_run.py", "print('review')\n")

        _write(
            root / "skills" / "aidd-core" / "SKILL.md",
            """---
name: aidd-core
user-invocable: false
---
""",
        )
        _write(root / "skills" / "aidd-core" / "runtime" / "runtime.py", "print('shared')\n")
        _write(root / "skills" / "aidd-core" / "templates" / "workspace-agents.md", "# workspace agents\n")

        _write(
            root / "agents" / "planner.md",
            """---
name: planner
skills:
  - feature-dev-aidd:aidd-core
---
""",
        )
        _write(
            root / "agents" / "validator.md",
            """---
name: validator
skills:
  - feature-dev-aidd:aidd-core
---
""",
        )
        _write(
            root / "agents" / "spec-interview-writer.md",
            """---
name: spec-interview-writer
skills:
  - feature-dev-aidd:aidd-core
---
""",
        )

        _write(
            root / "hooks" / "hooks.json",
            json.dumps(
                {
                    "hooks": {
                        "Stop": [
                            {
                                "matcher": ".*",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "${CLAUDE_PLUGIN_ROOT}/hooks/gate-workflow.sh",
                                    }
                                ],
                            }
                        ]
                    }
                }
            )
            + "\n",
        )
        _write(
            root / "hooks" / "gate-workflow.sh",
            "#!/usr/bin/env bash\npython3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_run.py --ticket TST-001\n",
        )

        _write(
            root / "skills" / "aidd-init" / "runtime" / "init.py",
            "SKILL_TEMPLATE_SEEDS = (\n"
            "  ('skills/aidd-core/templates/workspace-agents.md', 'AGENTS.md'),\n"
            ")\n",
        )

        _write(
            root / "docs" / "memory-v2-rfc.md",
            "# RFC\n\nStatus: Draft\n\n- `skills/aidd-memory/runtime/memory_extract.py`\n",
        )
        _write(
            root / "docs" / "legacy-draft.md",
            "# Legacy\n\nStatus: Draft\n\n- `skills/legacy/runtime/missing.py`\n",
        )
        _write(
            root / "backlog.md",
            "- [ ] **W101-14** memory docs `docs/memory-v2-rfc.md`\n",
        )
        _write(
            root / "tests" / "test_runtime_ref.py",
            "RUNTIME = 'skills/review/runtime/review_run.py'\n",
        )

    def test_command_to_subagent_links_and_no_subagent_case(self) -> None:
        with tempfile.TemporaryDirectory(prefix="repo-topology-subagent-") as tmp:
            root = Path(tmp)
            self._build_fixture_repo(root)
            payload = self.audit.build_revision_payload(root, generated_at="2026-02-24T00:00:00Z")

            command_edges = [
                edge
                for edge in payload.get("edges", [])
                if edge.get("type") == "command_subagent"
                and edge.get("source") == "command_skill:plan-new"
            ]
            targets = sorted(edge.get("target") for edge in command_edges)
            self.assertEqual(targets, ["agent:planner", "agent:validator"])

            spec_edges = [
                edge
                for edge in payload.get("edges", [])
                if edge.get("type") == "command_subagent"
                and edge.get("source") == "command_skill:spec-interview"
            ]
            self.assertEqual([edge.get("target") for edge in spec_edges], ["agent:spec-interview-writer"])

    def test_deterministic_payload_with_fixed_timestamp(self) -> None:
        with tempfile.TemporaryDirectory(prefix="repo-topology-deterministic-") as tmp:
            root = Path(tmp)
            self._build_fixture_repo(root)
            first = self.audit.build_revision_payload(root, generated_at="2026-02-24T00:00:00Z")
            second = self.audit.build_revision_payload(root, generated_at="2026-02-24T00:00:00Z")
            self.assertEqual(
                json.dumps(first, ensure_ascii=False, sort_keys=True),
                json.dumps(second, ensure_ascii=False, sort_keys=True),
            )

    def test_candidates_follow_current_triage_rules(self) -> None:
        with tempfile.TemporaryDirectory(prefix="repo-topology-candidates-") as tmp:
            root = Path(tmp)
            self._build_fixture_repo(root)
            payload = self.audit.build_revision_payload(root, generated_at="2026-02-24T00:00:00Z")
            candidates = payload.get("unused", {}).get("candidates", [])
            by_path = {item.get("path"): item for item in candidates}

            self.assertNotIn("agents/spec-interview-writer.md", by_path)

            self.assertNotIn("skills/review/runtime/context_pack.py", by_path)

            self.assertNotIn("docs/memory-v2-rfc.md", by_path)
            self.assertIn("docs/legacy-draft.md", by_path)
            self.assertEqual(by_path["docs/legacy-draft.md"].get("kind"), "draft_doc_missing_runtime_paths")

    def test_parts_modules_not_marked_as_unused_candidates(self) -> None:
        with tempfile.TemporaryDirectory(prefix="repo-topology-parts-") as tmp:
            root = Path(tmp)
            self._build_fixture_repo(root)
            payload = self.audit.build_revision_payload(root, generated_at="2026-02-24T00:00:00Z")
            candidates = payload.get("unused", {}).get("candidates", [])
            candidate_paths = {item.get("path") for item in candidates}
            self.assertNotIn("skills/qa/runtime/qa_parts/core.py", candidate_paths)
            self.assertNotIn("skills/qa/runtime/qa_parts/__init__.py", candidate_paths)

            runtime_dynamic_edges = [
                edge
                for edge in payload.get("edges", [])
                if edge.get("type") == "runtime_dynamic_load"
                and edge.get("source") == "runtime_py:skills/qa/runtime/qa.py"
            ]
            targets = {edge.get("target") for edge in runtime_dynamic_edges}
            self.assertIn("runtime_py:skills/qa/runtime/qa_parts/core.py", targets)

    def test_markdown_findings_are_dynamic(self) -> None:
        with tempfile.TemporaryDirectory(prefix="repo-topology-markdown-") as tmp:
            root = Path(tmp)
            self._build_fixture_repo(root)
            payload = self.audit.build_revision_payload(root, generated_at="2026-02-24T00:00:00Z")
            report = self.audit._render_markdown(payload)
            self.assertIn("Key findings:", report)
            self.assertNotIn("Обязательные находки:", report)
            self.assertIn("docs/legacy-draft.md", report)
            self.assertNotIn("docs/memory-v2-rfc.md", report)


if __name__ == "__main__":
    unittest.main()

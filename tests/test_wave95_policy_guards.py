import json
import re
import unittest

from tests.helpers import REPO_ROOT


class Wave95PolicyGuards(unittest.TestCase):
    def test_ci_workflow_contains_smoke_runtime_filter(self) -> None:
        ci_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        text = ci_path.read_text(encoding="utf-8")
        self.assertIn("smoke-workflow:", text)
        self.assertIn("dorny/paths-filter@v3", text)
        self.assertIn("skills/**", text)
        self.assertIn("hooks/**", text)
        self.assertIn("tools/**", text)
        self.assertIn("agents/**", text)
        self.assertIn("templates/aidd/**", text)
        self.assertIn("No runtime changes; skipping smoke", text)

    def test_ci_workflow_contains_dependency_review(self) -> None:
        ci_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        text = ci_path.read_text(encoding="utf-8")
        self.assertIn("dependency-review:", text)
        self.assertIn("actions/dependency-review-action@v4", text)
        self.assertIn("fail-on-severity: high", text)

    def test_marketplace_ref_is_not_feature_branch(self) -> None:
        marketplace_path = REPO_ROOT / ".claude-plugin" / "marketplace.json"
        payload = json.loads(marketplace_path.read_text(encoding="utf-8"))
        forbidden = re.compile(r"^(codex/wave[^/]*|feature/.+|codex/feature/.+)$")
        for plugin in payload.get("plugins", []):
            source = plugin.get("source") if isinstance(plugin, dict) else None
            ref = str(source.get("ref") or "").strip() if isinstance(source, dict) else ""
            self.assertFalse(
                bool(ref and forbidden.match(ref)),
                f"marketplace ref must be stable, got {ref!r}",
            )

    def test_hooks_do_not_reference_api_contract_placeholder(self) -> None:
        hook_script = REPO_ROOT / "hooks" / "gate-api-contract.sh"
        self.assertFalse(hook_script.exists(), "placeholder gate-api-contract hook should be removed")

        hooks_path = REPO_ROOT / "hooks" / "hooks.json"
        hooks_payload = json.loads(hooks_path.read_text(encoding="utf-8"))
        commands = [
            hook.get("command", "")
            for entries in hooks_payload.get("hooks", {}).values()
            for entry in entries
            for hook in entry.get("hooks", [])
            if isinstance(hook, dict)
        ]
        self.assertFalse(any("gate-api-contract" in cmd for cmd in commands))

    def test_prd_review_gate_is_single_authority(self) -> None:
        legacy_hook = REPO_ROOT / "hooks" / "gate-prd-review.sh"
        self.assertFalse(legacy_hook.exists(), "legacy PRD gate hook should be removed")

        hooks_path = REPO_ROOT / "hooks" / "hooks.json"
        hooks_payload = json.loads(hooks_path.read_text(encoding="utf-8"))
        commands = [
            hook.get("command", "")
            for entries in hooks_payload.get("hooks", {}).values()
            for entry in entries
            for hook in entry.get("hooks", [])
            if isinstance(hook, dict)
        ]
        self.assertFalse(any("gate-prd-review" in cmd for cmd in commands))
        self.assertTrue(any("gate-workflow.sh" in cmd for cmd in commands))


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT


class RlmSchemaTests(unittest.TestCase):
    def _load_schema(self, name: str) -> dict:
        path = REPO_ROOT / "tools" / "schemas" / name
        return json.loads(path.read_text(encoding="utf-8"))

    def test_node_schema_required_fields(self) -> None:
        schema = self._load_schema("rlm_node.schema.json")
        self.assertEqual(schema.get("schema_version"), "v1")
        required_common = schema.get("required_common") or []
        self.assertIn("schema", required_common)
        self.assertIn("schema_version", required_common)
        self.assertIn("node_kind", required_common)
        self.assertIn("id", required_common)

        kinds = schema.get("kinds") or {}
        file_required = (kinds.get("file") or {}).get("required") or []
        for key in (
            "file_id",
            "path",
            "rev_sha",
            "lang",
            "prompt_version",
            "summary",
            "public_symbols",
            "key_calls",
            "framework_roles",
            "test_hooks",
            "risks",
            "verification",
            "missing_tokens",
        ):
            self.assertIn(key, file_required)

        dir_required = (kinds.get("dir") or {}).get("required") or []
        for key in ("dir_id", "path", "children_file_ids", "children_count_total", "summary"):
            self.assertIn(key, dir_required)

    def test_link_schema_required_fields(self) -> None:
        schema = self._load_schema("rlm_link.schema.json")
        self.assertEqual(schema.get("schema_version"), "v1")
        required = schema.get("required") or []
        for key in (
            "schema",
            "schema_version",
            "link_id",
            "src_file_id",
            "dst_file_id",
            "type",
            "evidence_ref",
            "unverified",
        ):
            self.assertIn(key, required)

        evidence = schema.get("evidence_ref") or {}
        evidence_required = evidence.get("required") or []
        for key in ("path", "line_start", "line_end", "extractor", "match_hash"):
            self.assertIn(key, evidence_required)


if __name__ == "__main__":
    unittest.main()

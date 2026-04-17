import io
import json
import unittest
from contextlib import redirect_stdout

from aidd_runtime import loop_run as loop_run_module
from aidd_runtime import loop_step as loop_step_module


class LoopInvocationContractTests(unittest.TestCase):
    def test_loop_run_enrich_invocation_contract_sets_reinvoke_fields(self) -> None:
        payload = loop_run_module._enrich_invocation_contract(  # noqa: SLF001 - contract-level helper
            {
                "status": "blocked",
                "reason_code": "project_contract_missing",
            }
        )
        self.assertTrue(payload.get("invocation_terminal"))
        self.assertTrue(payload.get("reinvoke_allowed"))
        self.assertEqual(payload.get("retry_scope"), "invocation")
        self.assertEqual(payload.get("primary_reason"), "project_contract_missing")
        self.assertEqual(payload.get("secondary_symptom"), "no_top_level_result")

    def test_loop_step_emit_result_sets_invocation_contract_fields(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = loop_step_module.emit_result(
                "json",
                ticket="DEMO-LOOP",
                stage="implement",
                status="blocked",
                code=loop_step_module.BLOCKED_CODE,
                log_path="aidd/reports/loops/DEMO-LOOP/loop.step.log",
                reason="tests command path mismatch",
                reason_code="tests_cwd_mismatch",
                work_item_key="iteration_id=I1",
                scope_key="iteration_id_I1",
            )

        self.assertEqual(code, loop_step_module.BLOCKED_CODE)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload.get("invocation_terminal"))
        self.assertTrue(payload.get("reinvoke_allowed"))
        self.assertEqual(payload.get("retry_scope"), "invocation")
        self.assertEqual(payload.get("primary_reason"), "tests_cwd_mismatch")


if __name__ == "__main__":
    unittest.main()


from .helpers import ensure_gates_config, run_hook, write_active_feature, write_file

PAYLOAD_CONTROLLER = '{"tool_input":{"file_path":"src/main/kotlin/web/OrderController.kt"}}'
PAYLOAD_DOC = '{"tool_input":{"file_path":"docs/api/demo-checkout.yaml"}}'


def test_allows_when_config_absent(tmp_path):
    write_file(tmp_path, "src/main/kotlin/web/OrderController.kt", "class OrderController")
    write_active_feature(tmp_path, "demo-checkout")

    result = run_hook(tmp_path, "gate-api-contract.sh", PAYLOAD_CONTROLLER)
    assert result.returncode == 0, result.stderr


def test_allows_when_disabled(tmp_path):
    ensure_gates_config(tmp_path, {"api_contract": False})
    write_file(tmp_path, "src/main/kotlin/web/OrderController.kt", "class OrderController")
    write_active_feature(tmp_path, "demo-checkout")

    result = run_hook(tmp_path, "gate-api-contract.sh", PAYLOAD_CONTROLLER)
    assert result.returncode == 0, result.stderr


def test_blocks_when_contract_missing(tmp_path):
    ensure_gates_config(tmp_path, {})
    write_file(tmp_path, "src/main/kotlin/web/OrderController.kt", "class OrderController")
    write_active_feature(tmp_path, "demo-checkout")

    result = run_hook(tmp_path, "gate-api-contract.sh", PAYLOAD_CONTROLLER)
    assert result.returncode == 2
    assert "нет API контракта" in result.stderr


def test_allows_when_contract_present(tmp_path):
    ensure_gates_config(tmp_path, {})
    write_file(tmp_path, "src/main/kotlin/web/OrderController.kt", "class OrderController")
    write_active_feature(tmp_path, "demo-checkout")
    write_file(tmp_path, "docs/api/demo-checkout.yaml", "openapi: 3.0.0")

    result = run_hook(tmp_path, "gate-api-contract.sh", PAYLOAD_CONTROLLER)
    assert result.returncode == 0, result.stderr


def test_non_controller_edits_pass(tmp_path):
    ensure_gates_config(tmp_path, {})
    write_active_feature(tmp_path, "demo-checkout")

    result = run_hook(tmp_path, "gate-api-contract.sh", PAYLOAD_DOC)
    assert result.returncode == 0, result.stderr


def test_allows_when_slug_file_missing(tmp_path):
    ensure_gates_config(tmp_path, {})
    write_file(tmp_path, "src/main/kotlin/web/OrderController.kt", "class OrderController")
    # slug file intentionally not created

    result = run_hook(tmp_path, "gate-api-contract.sh", PAYLOAD_CONTROLLER)
    assert result.returncode == 0, result.stderr

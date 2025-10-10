import subprocess

from .helpers import ensure_gates_config, git_config_user, git_init, run_hook, write_file

ENTITY_PAYLOAD = '{"tool_input":{"file_path":"src/main/kotlin/entity/Order.kt"}}'
DOC_PAYLOAD = '{"tool_input":{"file_path":"docs/schema-notes.md"}}'


def test_allows_when_config_absent(tmp_path):
    git_init(tmp_path)
    write_file(tmp_path, "src/main/kotlin/entity/Order.kt", "data class Order")

    result = run_hook(tmp_path, "gate-db-migration.sh", ENTITY_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_allows_when_disabled(tmp_path):
    git_init(tmp_path)
    ensure_gates_config(tmp_path, {"db_migration": False})
    write_file(tmp_path, "src/main/kotlin/entity/Order.kt", "data class Order")

    result = run_hook(tmp_path, "gate-db-migration.sh", ENTITY_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_blocks_without_migration(tmp_path):
    git_init(tmp_path)
    ensure_gates_config(tmp_path, {})
    write_file(tmp_path, "src/main/kotlin/entity/Order.kt", "data class Order")

    result = run_hook(tmp_path, "gate-db-migration.sh", ENTITY_PAYLOAD)
    assert result.returncode == 2
    assert "миграции" in (result.stderr or "")


def test_allows_with_untracked_migration(tmp_path):
    git_init(tmp_path)
    ensure_gates_config(tmp_path, {})
    write_file(tmp_path, "src/main/kotlin/entity/Order.kt", "data class Order")
    write_file(tmp_path, "src/main/resources/db/migration/V1__demo.sql", "select 1;")

    result = run_hook(tmp_path, "gate-db-migration.sh", ENTITY_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_allows_with_tracked_migration(tmp_path):
    git_init(tmp_path)
    git_config_user(tmp_path)
    ensure_gates_config(tmp_path, {})
    write_file(tmp_path, "README.md", "demo")  # initial commit content
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: bootstrap"], cwd=tmp_path, check=True, capture_output=True)

    write_file(tmp_path, "src/main/kotlin/entity/Order.kt", "data class Order")
    write_file(tmp_path, "src/main/resources/db/migration/V2__demo.sql", "select 1;")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)

    result = run_hook(tmp_path, "gate-db-migration.sh", ENTITY_PAYLOAD)
    assert result.returncode == 0, result.stderr


def test_non_trigger_paths_pass(tmp_path):
    git_init(tmp_path)
    ensure_gates_config(tmp_path, {})
    write_file(tmp_path, "docs/schema-notes.md", "notes")

    result = run_hook(tmp_path, "gate-db-migration.sh", DOC_PAYLOAD)
    assert result.returncode == 0, result.stderr

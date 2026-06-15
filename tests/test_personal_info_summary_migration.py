from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import call, patch


def test_downgrade_removes_duplicate_personal_info_rows_before_restoring_constraint():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "1c2d3e4f5a6b_add_personal_info_summary_to_users.py"
    )
    spec = spec_from_file_location("personal_info_summary_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    with patch.object(migration, "op") as op_mock:
        migration.downgrade()

    execute_calls = [mock_call for mock_call in op_mock.mock_calls if mock_call[0] == "execute"]
    assert execute_calls, "expected duplicate-cleanup SQL before recreating the unique constraint"
    cleanup_sql = execute_calls[0].args[0]
    assert "ROW_NUMBER()" in cleanup_sql
    assert "category = 'personal_info'" in cleanup_sql
    assert (
        call.create_unique_constraint(
            "uq_memory_items_user_category_key",
            "memory_items",
            ["user_id", "category", "key"],
        )
        in op_mock.mock_calls
    )

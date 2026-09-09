from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import Boolean, Integer


def _load_migration():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "a3b7c9d1e5f2_add_recall_queue_portion_provenance.py"
    )
    spec = spec_from_file_location("recall_queue_portion_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_upgrade_adds_provenance_and_updates_priority_default():
    migration = _load_migration()

    with patch.object(migration, "op") as op_mock:
        migration.upgrade()

    op_mock.get_bind.assert_called_once_with()
    bind = op_mock.get_bind.return_value
    assert [str(call.args[0]) for call in bind.execute.call_args_list] == [
        "SET LOCAL lock_timeout = '5s'",
        "SET LOCAL statement_timeout = '60s'",
    ]

    add_args = op_mock.add_column.call_args.args
    assert add_args[0] == "recall_queue_items"
    column = add_args[1]
    assert column.name == "is_unstudied_extra"
    assert isinstance(column.type, Boolean)
    assert column.nullable is False
    assert str(column.server_default.arg) == "false"

    alter_args = op_mock.alter_column.call_args
    assert alter_args.args[:2] == ("vocabulary", "priority_learn")
    assert isinstance(alter_args.kwargs["existing_type"], Integer)
    assert alter_args.kwargs["server_default"] == "5"


def test_downgrade_restores_priority_default_and_drops_provenance():
    migration = _load_migration()

    with patch.object(migration, "op") as op_mock:
        migration.downgrade()

    alter_args = op_mock.alter_column.call_args
    assert alter_args.args[:2] == ("vocabulary", "priority_learn")
    assert isinstance(alter_args.kwargs["existing_type"], Integer)
    assert alter_args.kwargs["server_default"] == "9"
    op_mock.drop_column.assert_called_once_with("recall_queue_items", "is_unstudied_extra")

"""Tests for the file-backed Telegram offset store."""

from runestone.state.telegram_update_offset_store import TelegramUpdateOffsetStore


def test_get_update_offset_defaults_to_zero(tmp_path):
    store = TelegramUpdateOffsetStore(str(tmp_path / "offset.txt"))

    assert store.get_update_offset() == 0


def test_set_update_offset_persists_value(tmp_path):
    offset_path = tmp_path / "offset.txt"
    store = TelegramUpdateOffsetStore(str(offset_path))

    store.set_update_offset(42)

    assert store.get_update_offset() == 42
    assert offset_path.read_text() == "42"


def test_get_update_offset_returns_zero_on_invalid_contents(tmp_path):
    offset_path = tmp_path / "offset.txt"
    offset_path.write_text("not-an-int")
    store = TelegramUpdateOffsetStore(str(offset_path))

    assert store.get_update_offset() == 0

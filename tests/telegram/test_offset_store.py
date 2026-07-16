from runestone.telegram.offset_store import TelegramUpdateOffsetStore


def test_get_update_offset_defaults_to_zero(tmp_path):
    store = TelegramUpdateOffsetStore(str(tmp_path / "offset.txt"))

    assert store.get_update_offset() == 0


def test_set_update_offset_persists_value(tmp_path):
    store = TelegramUpdateOffsetStore(str(tmp_path / "nested" / "offset.txt"))

    store.set_update_offset(42)

    assert store.get_update_offset() == 42


def test_set_update_offset_supports_bare_filename(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = TelegramUpdateOffsetStore("offset.txt")

    store.set_update_offset(7)

    assert store.get_update_offset() == 7


def test_get_update_offset_returns_zero_for_malformed_content(tmp_path):
    offset_path = tmp_path / "offset.txt"
    offset_path.write_text("invalid")

    assert TelegramUpdateOffsetStore(str(offset_path)).get_update_offset() == 0

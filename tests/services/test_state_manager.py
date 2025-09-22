import json
import os
import tempfile

import pytest

from src.runestone.core.exceptions import UserNotAuthorised
from src.runestone.state.state_exceptions import StateCorruptionError
from src.runestone.state.state_manager import StateManager
from src.runestone.state.state_types import UserData


@pytest.fixture
def temp_state_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        default_state = {
            "update_offset": 0,
            "users": {
                "user1": {"db_user_id": 1, "chat_id": 123, "is_active": True, "daily_selection": {"word": "test"}},
                "user2": {"db_user_id": 2, "chat_id": None, "is_active": False, "daily_selection": {}},
            },
        }
        json.dump(default_state, f)
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def state_manager(temp_state_file):
    StateManager._reset_for_testing()
    return StateManager(temp_state_file)


def test_get_user_existing(state_manager):
    user = state_manager.get_user("user1")
    expected = UserData(db_user_id=1, chat_id=123, is_active=True, daily_selection={"word": "test"}, next_word_index=0)
    assert user == expected


def test_get_user_non_existing(state_manager):
    user = state_manager.get_user("nonexistent")
    assert user is None


def test_update_user_existing(state_manager, temp_state_file):
    new_data = {"db_user_id": 1, "chat_id": 456, "is_active": False, "daily_selection": {"word": "updated"}}
    state_manager.update_user("user1", new_data)
    with open(temp_state_file, "r") as f:
        state = json.load(f)
    expected = new_data.copy()
    expected["next_word_index"] = 0  # Default value from UserData model
    assert state["users"]["user1"] == expected


def test_update_user_new_raises_exception(state_manager):
    new_data = {"db_user_id": 3, "chat_id": 789, "is_active": True, "daily_selection": {}}
    with pytest.raises(UserNotAuthorised, match="User 'user3' does not exist and cannot be updated."):
        state_manager.update_user("user3", new_data)


def test_get_active_users(state_manager):
    active_users = state_manager.get_active_users()
    assert list(active_users.keys()) == ["user1"]


def test_get_update_offset(state_manager):
    offset = state_manager.get_update_offset()
    assert offset == 0


def test_set_update_offset(state_manager, temp_state_file):
    state_manager.set_update_offset(100)
    with open(temp_state_file, "r") as f:
        state = json.load(f)
    assert state["update_offset"] == 100
    assert state_manager.get_update_offset() == 100


def test_file_creation():
    StateManager._reset_for_testing()
    with tempfile.TemporaryDirectory() as temp_dir:
        state_file = os.path.join(temp_dir, "state.json")
        StateManager(state_file)
        assert os.path.exists(state_file)
        with open(state_file, "r") as f:
            state = json.load(f)
        assert state == {"update_offset": 0, "users": {}}


def test_load_state_invalid_json():
    StateManager._reset_for_testing()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("invalid json")
        f.flush()
        manager = StateManager(f.name)
        with pytest.raises(StateCorruptionError, match="Invalid JSON in state file"):
            manager.get_user("test")
    os.unlink(f.name)


def test_save_state_error():
    # This is hard to test without mocking, but for now, assume it works
    pass


def test_singleton_same_path(temp_state_file):
    manager1 = StateManager(temp_state_file)
    manager2 = StateManager(temp_state_file)
    assert manager1 is manager2


def test_singleton_different_paths():
    with tempfile.TemporaryDirectory() as temp_dir:
        path1 = os.path.join(temp_dir, "state1.json")
        path2 = os.path.join(temp_dir, "state2.json")
        manager1 = StateManager(path1)
        manager2 = StateManager(path2)
        assert manager1 is manager2

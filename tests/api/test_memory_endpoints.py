from runestone.api.memory_item_schemas import MemoryCategory, PersonalInfoStatus
from runestone.db.models import MemoryItem


async def test_list_memory_items_supports_legacy_status_query_param(client):
    db = client.db
    user = client.user
    db.add_all(
        [
            MemoryItem(
                user_id=user.id,
                category=MemoryCategory.PERSONAL_INFO.value,
                key="goal",
                content="Practice speaking",
                status=PersonalInfoStatus.ACTIVE.value,
            ),
            MemoryItem(
                user_id=user.id,
                category=MemoryCategory.PERSONAL_INFO.value,
                key="old_goal",
                content="Old practice goal",
                status=PersonalInfoStatus.OUTDATED.value,
            ),
        ]
    )
    await db.commit()

    response = await client.get("/api/memory", params={"category": "personal_info", "status": "active"})

    assert response.status_code == 200
    assert [item["key"] for item in response.json()] == ["goal"]


async def test_get_memory_maintenance_status_running(client):
    # Mock the behavior of is_memory_maintenance_running
    client.app.state.agents_manager.is_memory_maintenance_running.return_value = True

    response = await client.get("/api/memory/maintenance-status")

    assert response.status_code == 200
    assert response.json() == {"running": True}
    client.app.state.agents_manager.is_memory_maintenance_running.assert_called_once_with(client.user.id)


async def test_get_memory_maintenance_status_not_running(client):
    # Mock the behavior of is_memory_maintenance_running
    client.app.state.agents_manager.is_memory_maintenance_running.return_value = False

    response = await client.get("/api/memory/maintenance-status")

    assert response.status_code == 200
    assert response.json() == {"running": False}
    client.app.state.agents_manager.is_memory_maintenance_running.assert_called_once_with(client.user.id)

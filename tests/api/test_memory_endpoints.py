from runestone.api.memory_item_schemas import MemoryCategory
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
                status="active",
            ),
            MemoryItem(
                user_id=user.id,
                category=MemoryCategory.PERSONAL_INFO.value,
                key="old_goal",
                content="Old practice goal",
                status="outdated",
            ),
        ]
    )
    await db.commit()

    response = await client.get("/api/memory", params={"category": "personal_info", "status": "active"})

    assert response.status_code == 200
    assert [item["key"] for item in response.json()] == ["goal"]


async def test_create_memory_item_is_create_only_and_update_uses_id_endpoint(client):
    create_response = await client.post(
        "/api/memory",
        json={"category": "personal_info", "key": "goal", "content": "Practice speaking"},
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["key"] == "goal"
    assert created["content"] == "Practice speaking"

    duplicate_response = await client.post(
        "/api/memory",
        json={"category": "personal_info", "key": "goal", "content": "Practice grammar"},
    )
    assert duplicate_response.status_code == 400

    update_response = await client.put(
        f"/api/memory/{created['id']}",
        json={"key": "updated_goal", "content": "Practice grammar"},
    )
    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["key"] == "updated_goal"
    assert payload["content"] == "Practice grammar"


async def test_update_memory_item_status_rejects_personal_info(client):
    db = client.db
    user = client.user
    item = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.PERSONAL_INFO.value,
        key="goal",
        content="Practice speaking",
        status="active",
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    response = await client.put(f"/api/memory/{item.id}/status", json={"status": "outdated"})

    assert response.status_code == 400
    assert "not supported" in response.json()["detail"]


async def test_update_memory_item_rejects_non_active_personal_info(client):
    db = client.db
    user = client.user
    item = MemoryItem(
        user_id=user.id,
        category=MemoryCategory.PERSONAL_INFO.value,
        key="goal",
        content="Practice speaking",
        status="correction",
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    response = await client.put(
        f"/api/memory/{item.id}",
        json={"key": "goal", "content": "Practice reading"},
    )

    assert response.status_code == 400
    assert "only be edited while active" in response.json()["detail"]


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

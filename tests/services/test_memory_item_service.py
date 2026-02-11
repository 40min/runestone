from datetime import datetime, timedelta, timezone

from runestone.db.memory_item_repository import MemoryItemRepository
from runestone.db.models import MemoryItem
from runestone.services.memory_item_service import MemoryItemService


def test_cleanup_old_mastered_areas(db_with_test_user, monkeypatch):
    db, user = db_with_test_user
    repo = MemoryItemRepository(db)
    service = MemoryItemService(repo)

    fixed_now = datetime(2026, 2, 11, tzinfo=timezone.utc)
    monkeypatch.setattr(service, "_utc_now", lambda: fixed_now)

    old = fixed_now - timedelta(days=120)
    recent = fixed_now - timedelta(days=10)

    db.add_all(
        [
            # Deleted: status_changed_at old (even if updated_at is recent)
            MemoryItem(
                user_id=user.id,
                category="area_to_improve",
                key="old_mastered_status_changed",
                content="Old mastered",
                status="mastered",
                status_changed_at=old,
                updated_at=recent,
            ),
            # Deleted: no status_changed_at, but updated_at old
            MemoryItem(
                user_id=user.id,
                category="area_to_improve",
                key="old_mastered_updated",
                content="Old mastered",
                status="mastered",
                status_changed_at=None,
                updated_at=old,
            ),
            # Kept: mastered but recent
            MemoryItem(
                user_id=user.id,
                category="area_to_improve",
                key="recent_mastered",
                content="Recent mastered",
                status="mastered",
                status_changed_at=recent,
                updated_at=recent,
            ),
            # Kept: old but not mastered
            MemoryItem(
                user_id=user.id,
                category="area_to_improve",
                key="old_struggling",
                content="Still struggling",
                status="struggling",
                status_changed_at=old,
                updated_at=old,
            ),
            # Kept: different category entirely
            MemoryItem(
                user_id=user.id,
                category="knowledge_strength",
                key="strength_old",
                content="Strength",
                status="active",
                status_changed_at=old,
                updated_at=old,
            ),
        ]
    )
    db.commit()

    deleted = service.cleanup_old_mastered_areas(user.id, older_than_days=90)
    assert deleted == 2

    remaining_keys = {item.key for item in db.query(MemoryItem).filter(MemoryItem.user_id == user.id).all()}
    assert remaining_keys == {"recent_mastered", "old_struggling", "strength_old"}

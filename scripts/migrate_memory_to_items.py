import json
import logging
import os
import sys

# Add src to sys.path to allow imports from runestone
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from runestone.db.database import SessionLocal  # noqa: E402
from runestone.db.memory_item_repository import MemoryItemRepository  # noqa: E402
from runestone.db.models import MemoryItem, User  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_user_memory(db, user, memory_repo):
    """Migrate legacy JSON memory columns to memory_items table."""
    # Mapping old columns (JSON strings) to new categories
    migration_map = {
        "personal_info": "personal_info",
        "areas_to_improve": "area_to_improve",
        "knowledge_strengths": "knowledge_strength",
    }

    for old_col, new_cat in migration_map.items():
        data_str = getattr(user, old_col)
        if not data_str:
            continue

        try:
            # Handle empty strings or plain text that isn't JSON
            if not data_str.strip() or not (data_str.strip().startswith("{") or data_str.strip().startswith("[")):
                if data_str.strip():
                    logger.warning(f"User {user.id} has non-JSON data in {old_col}: {data_str[:50]}...")
                continue

            data = json.loads(data_str)
            if not isinstance(data, dict):
                logger.warning(f"User {user.id} has invalid JSON in {old_col}: {data_str[:50]}...")
                continue

            for key, content in data.items():
                if not key or not content:
                    continue

                # Avoid duplicates
                existing = memory_repo.get_by_user_category_key(user.id, new_cat, key)
                if not existing:
                    # Map old data to new status
                    status = "active"
                    if new_cat == "area_to_improve":
                        status = "struggling"
                    elif new_cat == "knowledge_strength":
                        status = "mastered"

                    item = MemoryItem(user_id=user.id, category=new_cat, key=key, content=str(content), status=status)
                    db.add(item)
                    logger.info(f"  + Migrated {new_cat}:{key} for user {user.id}")
        except json.JSONDecodeError:
            logger.error(f"  ! Failed to parse JSON for user {user.id} in {old_col}")


def main():
    db = SessionLocal()
    try:
        memory_repo = MemoryItemRepository(db)

        # Get all non-migrated users
        # We use a explicit boolean check that works across backends
        users = db.query(User).filter(User.memory_migrated.is_(False)).all()

        if not users:
            logger.info("No users found for migration.")
            return

        logger.info(f"Found {len(users)} users to migrate.")

        for user in users:
            logger.info(f"Processing user {user.id} ({user.email})...")
            migrate_user_memory(db, user, memory_repo)
            user.memory_migrated = True
            db.commit()
            logger.info(f"User {user.id} migration marked as complete.")

        logger.info("Migration finished successfully.")

    except Exception:
        logger.exception("Migration failed")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

import os
import sqlite3

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

# Load environment variables
load_dotenv()

SQLITE_DB = os.getenv("SQLITE_DB_PATH", "state/runestone.db")
POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql://runestone:runestone@localhost:5432/runestone")
# Convert asyncpg URL to psycopg2 URL if needed
IF_POSTGRES_URL = POSTGRES_URL.replace("postgresql+asyncpg://", "postgresql://")

TABLES = [
    "users",
    "vocabulary",
    "chat_sessions",
    "chat_messages",
    "memory_items",
]


def migrate():
    if not os.path.exists(SQLITE_DB):
        print(f"❌ SQLite database not found at {SQLITE_DB}")
        return

    print(f"🚀 Starting migration from {SQLITE_DB} to Postgres...")

    try:
        # Connect to SQLite
        sqlite_conn = sqlite3.connect(SQLITE_DB)
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()

        # Connect to Postgres
        pg_conn = psycopg2.connect(IF_POSTGRES_URL)
        pg_cursor = pg_conn.cursor()

        for table in TABLES:
            print(f"📦 Migrating table: {table}...")

            # Fetch data from SQLite
            sqlite_cursor.execute(f"SELECT * FROM {table}")
            rows = sqlite_cursor.fetchall()

            if not rows:
                print(f"   - Table {table} is empty. Skipping.")
                continue

            # Get column names
            columns = rows[0].keys()

            # Prepare insert query
            # Postgres doesn't like "(CURRENT_TIMESTAMP)" as a string value if it was meant to be a default,
            # but here we are inserting actual values.
            column_names = ", ".join(columns)
            placeholder = ", ".join(["%s"] * len(columns))
            insert_query = f"INSERT INTO {table} ({column_names}) VALUES ({placeholder}) ON CONFLICT DO NOTHING"

            # Convert rows to list of tuples
            data = [tuple(row) for row in rows]

            # Execute batch insert
            execute_values(pg_cursor, f"INSERT INTO {table} ({column_names}) VALUES %s ON CONFLICT DO NOTHING", data)
            print(f"   - Successfully migrated {len(rows)} rows to {table}.")

        # Commit changes
        pg_conn.commit()
        print("✅ Migration completed successfully!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        if "pg_conn" in locals():
            pg_conn.rollback()
    finally:
        if "sqlite_conn" in locals():
            sqlite_conn.close()
        if "pg_conn" in locals():
            pg_conn.close()


if __name__ == "__main__":
    migrate()

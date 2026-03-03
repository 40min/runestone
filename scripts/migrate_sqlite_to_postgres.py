import os
import sqlite3
from argparse import ArgumentParser

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

# Load environment variables
load_dotenv()

SQLITE_DB = os.getenv("SQLITE_DB_PATH", "state/runestone.db")
POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql://runestone:runestone@localhost:5432/runestone")
# Convert asyncpg URL to psycopg2 URL if needed
PSYCOPG2_DATABASE_URL = POSTGRES_URL.replace("postgresql+asyncpg://", "postgresql://").replace(
    "postgresql+psycopg2://", "postgresql://"
)

TABLES = [
    "users",
    "vocabulary",
    "chat_messages",
    "chat_summaries",
    "memory_items",
]


def parse_args():
    parser = ArgumentParser(description="Migrate data from SQLite to PostgreSQL.")
    parser.add_argument("--sqlite-path", default=SQLITE_DB, help="Path to SQLite DB file")
    parser.add_argument("--postgres-url", default=PSYCOPG2_DATABASE_URL, help="PostgreSQL connection URL")
    return parser.parse_args()


def _convert_to_bool(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "t", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "f", "no", "n", "off"}:
            return False
    return value


def migrate(sqlite_db: str, postgres_url: str):
    if not os.path.exists(sqlite_db):
        print(f"❌ SQLite database not found at {sqlite_db}")
        return

    print(f"🚀 Starting migration from {sqlite_db} to Postgres...")

    try:
        # Connect to SQLite
        sqlite_conn = sqlite3.connect(sqlite_db)
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()

        # Connect to Postgres
        pg_conn = psycopg2.connect(postgres_url)
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
            col_names = list(columns)

            column_names = ", ".join(columns)

            # Detect Postgres boolean columns and coerce SQLite values (often stored as 0/1).
            pg_cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                  AND data_type = 'boolean'
                """,
                (table,),
            )
            bool_cols = {r[0] for r in pg_cursor.fetchall()}

            # Convert rows to list of tuples
            data = []
            for row in rows:
                converted = []
                for col in col_names:
                    value = row[col]
                    if col in bool_cols:
                        value = _convert_to_bool(value)
                    converted.append(value)
                data.append(tuple(converted))

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
    args = parse_args()
    migrate(sqlite_db=args.sqlite_path, postgres_url=args.postgres_url)

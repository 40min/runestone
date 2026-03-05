#!/usr/bin/env bash
set -euo pipefail

# Reset PostgreSQL data for this docker-compose stack and restart services.
# WARNING: This permanently deletes all data in the Postgres volume.

if [[ "${1:-}" != "--yes" ]]; then
  echo "This will permanently delete PostgreSQL data for this stack."
  echo "Run again with: $0 --yes"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found"
  exit 1
fi

echo "Stopping stack and removing volumes..."
docker compose down -v --remove-orphans

echo "Starting fresh postgres..."
docker compose up -d postgres

echo "Starting backend + recall (migrations run on backend startup)..."
docker compose up -d backend recall

echo "Reset complete."
echo "Useful checks:"
echo "  docker compose ps"
echo "  docker compose logs --tail=200 backend"

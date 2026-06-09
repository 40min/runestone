#!/bin/sh

set -eu

BACKUP_DIR="${POSTGRES_BACKUP_DIR:-/backups}"
BACKUP_INTERVAL_SECONDS="${POSTGRES_BACKUP_INTERVAL_SECONDS:-86400}"
BACKUP_RETENTION_DAYS="${POSTGRES_BACKUP_RETENTION_DAYS:-7}"
PGHOST="${PGHOST:-postgres}"
PGPORT="${PGPORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:?POSTGRES_USER is required}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
POSTGRES_DB="${POSTGRES_DB:?POSTGRES_DB is required}"

export PGPASSWORD="${POSTGRES_PASSWORD}"

log() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

wait_for_postgres() {
  until pg_isready -h "${PGHOST}" -p "${PGPORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; do
    log "waiting for postgres at ${PGHOST}:${PGPORT}/${POSTGRES_DB}"
    sleep 5
  done
}

run_backup() {
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  tmp_file="${BACKUP_DIR}/${POSTGRES_DB}-${timestamp}.dump.tmp"
  final_file="${BACKUP_DIR}/${POSTGRES_DB}-${timestamp}.dump"

  log "starting backup to ${final_file}"
  if ! pg_dump \
    --format=custom \
    --no-acl \
    --no-owner \
    --host="${PGHOST}" \
    --port="${PGPORT}" \
    --username="${POSTGRES_USER}" \
    --file="${tmp_file}" \
    "${POSTGRES_DB}"; then
    rm -f "${tmp_file}"
    log "pg_dump failed, cleaned up temporary file"
    exit 1
  fi
  mv "${tmp_file}" "${final_file}"
  log "completed backup to ${final_file}"
}

prune_backups() {
  log "pruning backups older than ${BACKUP_RETENTION_DAYS} days from ${BACKUP_DIR}"
  # `find -mtime` rounds file ages down to whole 24-hour buckets, so `+6` is the closest match for a 7-day cutoff.
  retention_buckets=$((BACKUP_RETENTION_DAYS - 1))
  if [ "${retention_buckets}" -lt 0 ]; then
    retention_buckets=0
  fi
  find "${BACKUP_DIR}" -maxdepth 1 -type f -name "${POSTGRES_DB}-*.dump" -mtime "+${retention_buckets}" -exec rm -f {} \;
}

mkdir -p "${BACKUP_DIR}"
wait_for_postgres

while true; do
  run_backup
  prune_backups
  log "sleeping for ${BACKUP_INTERVAL_SECONDS} seconds"
  sleep "${BACKUP_INTERVAL_SECONDS}"
done

#!/usr/bin/env bash
# Back up the stock-agents Postgres database into ./backups/.
#
# Usage (from anywhere):
#   ./scripts/backup_db.sh
#
# Dumps via pg_dump inside the running postgres container (custom format,
# restorable with pg_restore), and copies the result out to backups/ with
# a timestamped filename. Requires the postgres container to be running
# (docker compose up postgres or the full stack).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Read just the two vars we need out of .env rather than sourcing the whole
# file — .env holds provider API keys whose values aren't valid shell syntax.
_env_get() {
    [ -f .env ] && grep -m1 "^${1}=" .env | cut -d= -f2- || true
}

POSTGRES_DB="$(_env_get POSTGRES_DB)"
POSTGRES_USER="$(_env_get POSTGRES_USER)"
POSTGRES_DB="${POSTGRES_DB:-stock_agents}"
POSTGRES_USER="${POSTGRES_USER:-sa_user}"

CONTAINER="$(docker compose ps -q postgres 2>/dev/null || true)"
if [ -z "$CONTAINER" ]; then
    # Fall back to a name match if `docker compose ps` can't resolve it
    # (e.g. run from outside the compose project directory).
    CONTAINER="$(docker ps --filter "name=postgres" --format '{{.Names}}' | head -1)"
fi
if [ -z "$CONTAINER" ]; then
    echo "ERROR: no running postgres container found. Start it with: docker compose up -d postgres" >&2
    exit 1
fi

mkdir -p backups
TS="$(date +%Y%m%d_%H%M%S)"
OUT="backups/stock_agents_${TS}.dump"
TMP_IN_CONTAINER="/tmp/backup_${TS}.dump"

echo "Backing up database '$POSTGRES_DB' from container '$CONTAINER'..."
docker exec "$CONTAINER" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -F c -f "$TMP_IN_CONTAINER"
docker cp "$CONTAINER:$TMP_IN_CONTAINER" "$OUT"
docker exec "$CONTAINER" rm -f "$TMP_IN_CONTAINER"

echo "Backup written to $OUT ($(du -h "$OUT" | cut -f1))"

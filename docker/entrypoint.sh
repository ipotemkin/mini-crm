#!/bin/sh
set -e

if [ -f /data/crm.sqlite3 ]; then
  python -m app.cli backup || true
fi

alembic upgrade head
exec "$@"

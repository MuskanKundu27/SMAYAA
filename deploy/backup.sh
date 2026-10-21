#!/usr/bin/env bash
# Nightly database backup, run by cron as root (see setup-server.sh). Keeps 14 days.
# Restore a backup:  sudo -u postgres pg_restore --clean -d smayaa /var/backups/smayaa/<file>.dump
set -euo pipefail

DIR=/var/backups/smayaa
FILE="$DIR/smayaa-$(date -u +%Y%m%d-%H%M).dump"

sudo -u postgres pg_dump -Fc smayaa > "$FILE.tmp"
mv "$FILE.tmp" "$FILE"
chmod 600 "$FILE"
find "$DIR" -name 'smayaa-*.dump' -mtime +14 -delete

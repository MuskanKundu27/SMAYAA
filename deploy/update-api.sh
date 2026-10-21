#!/usr/bin/env bash
# Deploy the latest code from GitHub (main) to the API. Run on the server:
#   sudo bash /opt/smayaa/app/deploy/update-api.sh
# Takes a backup first, so a bad migration can be undone with pg_restore.
set -euo pipefail

APP=/opt/smayaa/app
VENV=/opt/smayaa/venv

/usr/local/bin/smayaa-backup
sudo -u smayaa git -C "$APP" pull -q --ff-only
sudo -u smayaa "$VENV/bin/pip" install -q -e "$APP/api"
(cd "$APP/api" && sudo -u smayaa "$VENV/bin/alembic" upgrade head)
install -m 644 "$APP/deploy/smayaa-api.service" /etc/systemd/system/smayaa-api.service
systemctl daemon-reload
systemctl restart smayaa-api
sleep 2
curl -fsS http://127.0.0.1:8000/api/v1/health && echo && echo "API updated."

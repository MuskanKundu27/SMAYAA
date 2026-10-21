#!/usr/bin/env bash
# Deploy the latest code from GitHub (main) to the API. Run on the server:
#   sudo bash /opt/smayaa/app/deploy/update-api.sh
# Takes a backup first, so a bad migration can be undone with pg_restore.
set -euo pipefail

APP=/opt/smayaa/app
VENV=/opt/smayaa/venv
API_PORT=8000
# shellcheck disable=SC1091
[ -f /opt/smayaa/deploy.env ] && . /opt/smayaa/deploy.env   # port chosen by setup-server.sh

/usr/local/bin/smayaa-backup
sudo -u smayaa git -C "$APP" pull -q --ff-only
sudo -u smayaa "$VENV/bin/pip" install -q -e "$APP/api"
(cd "$APP/api" && sudo -u smayaa "$VENV/bin/alembic" upgrade head)
sed "s/__API_PORT__/$API_PORT/g" "$APP/deploy/smayaa-api.service" \
  > /etc/systemd/system/smayaa-api.service
systemctl daemon-reload
systemctl restart smayaa-api
sleep 2
curl -fsS "http://127.0.0.1:$API_PORT/api/v1/health" && echo && echo "API updated."

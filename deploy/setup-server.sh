#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 server for SMAYAA. Safe to run again: every step
# checks what already exists and skips it.
#
#   sudo bash setup-server.sh <hostname>
#   e.g. sudo bash setup-server.sh smayaa.3-110-175-240.sslip.io
#
# Result: PostgreSQL 16 (local only), the API as a systemd service on 127.0.0.1:8000,
# Caddy serving the web app with automatic HTTPS, and nightly database backups.
set -euo pipefail

HOST="${1:?usage: sudo bash setup-server.sh <hostname>}"
REPO_URL="https://github.com/MuskanKundu27/SMAYAA.git"
BASE=/opt/smayaa
APP="$BASE/app"          # git checkout (contains api/, web/, deploy/)
VENV="$BASE/venv"
WEB=/var/www/smayaa      # built web app, uploaded from a developer machine
BACKUPS=/var/backups/smayaa

[ "$(id -u)" -eq 0 ] || { echo "Run with sudo."; exit 1; }
step() { echo; echo "==> $*"; }

step "Swap file (1 GB) so small instances do not run out of memory"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 1G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

step "System packages"
apt-get update -q
apt-get install -y -q git python3.12-venv postgresql curl gpg debian-keyring \
  debian-archive-keyring apt-transport-https

step "Caddy web server (official repository)"
if ! command -v caddy >/dev/null; then
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -q
  apt-get install -y -q caddy
fi

step "Service account 'smayaa' (runs the API, owns the code)"
id smayaa >/dev/null 2>&1 || useradd --system --home-dir "$BASE" --shell /usr/sbin/nologin smayaa
mkdir -p "$BASE"
chown smayaa:smayaa "$BASE"

step "Code"
if [ ! -d "$APP/.git" ]; then
  sudo -u smayaa git clone -q "$REPO_URL" "$APP"
else
  sudo -u smayaa git -C "$APP" pull -q --ff-only
fi

step "Settings file $APP/.env (created once, never overwritten)"
if [ ! -f "$APP/.env" ]; then
  OWNER_PW=$(openssl rand -hex 24)
  APP_PW=$(openssl rand -hex 24)
  sudo -u postgres psql -q -v ON_ERROR_STOP=1 -v owner_pw="$OWNER_PW" -v app_pw="$APP_PW" <<'SQL'
SELECT format('CREATE ROLE smayaa_owner LOGIN PASSWORD %L', :'owner_pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smayaa_owner') \gexec
SELECT format('ALTER ROLE smayaa_owner PASSWORD %L', :'owner_pw') \gexec
SELECT format('CREATE ROLE smayaa_app LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD %L', :'app_pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smayaa_app') \gexec
SELECT format('ALTER ROLE smayaa_app PASSWORD %L', :'app_pw') \gexec
SELECT 'CREATE DATABASE smayaa OWNER smayaa_owner'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'smayaa') \gexec
SQL
  sudo -u postgres psql -q -v ON_ERROR_STOP=1 -d smayaa -f "$APP/api/scripts/grant_app_role.sql"
  umask 077
  cat > "$APP/.env" <<ENV
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://smayaa_app:${APP_PW}@127.0.0.1:5432/smayaa
MIGRATION_DATABASE_URL=postgresql+psycopg://smayaa_owner:${OWNER_PW}@127.0.0.1:5432/smayaa
JWT_SECRET=$(openssl rand -hex 32)
CORS_ORIGINS=https://${HOST}
LOG_LEVEL=INFO
ENV
  chown smayaa:smayaa "$APP/.env"
  chmod 600 "$APP/.env"
fi

step "Python environment and database migrations"
[ -d "$VENV" ] || sudo -u smayaa python3.12 -m venv "$VENV"
sudo -u smayaa "$VENV/bin/pip" install -q --upgrade pip
sudo -u smayaa "$VENV/bin/pip" install -q -e "$APP/api"
(cd "$APP/api" && sudo -u smayaa "$VENV/bin/alembic" upgrade head)

step "API service"
install -m 644 "$APP/deploy/smayaa-api.service" /etc/systemd/system/smayaa-api.service
systemctl daemon-reload
systemctl enable --now smayaa-api
systemctl restart smayaa-api

step "Web folder $WEB (filled by deploy/push-web.ps1 from a developer machine)"
mkdir -p "$WEB"
chmod 755 "$WEB"
[ -f "$WEB/index.html" ] || echo '<p>SMAYAA is being deployed. Upload the web app next.</p>' > "$WEB/index.html"

step "Caddy site for https://$HOST"
sed "s/__HOST__/$HOST/g" "$APP/deploy/Caddyfile" > /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
systemctl reload caddy || systemctl restart caddy

step "Nightly database backup (02:30 UTC, keeps 14 days, same server)"
mkdir -p "$BACKUPS"
chmod 700 "$BACKUPS"
install -m 755 "$APP/deploy/backup.sh" /usr/local/bin/smayaa-backup
echo '30 2 * * * root /usr/local/bin/smayaa-backup' > /etc/cron.d/smayaa-backup

step "Done"
echo "Open https://$HOST (the certificate can take a minute on first visit)."
echo "Next: upload the web app (deploy/push-web.ps1), then create the platform admin:"
echo "  cd $APP/api && sudo -u smayaa $VENV/bin/python -m app.scripts.create_platform_admin"

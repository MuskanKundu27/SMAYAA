#!/usr/bin/env bash
# One-time setup of an Ubuntu 24.04 server for SMAYAA. Safe to run again: every step checks
# what already exists and skips it. Designed to live next to other sites on a shared server:
# it only adds its own user, folders, database, service and web-server site.
#
#   sudo bash setup-server.sh <hostname>
#   e.g. sudo bash setup-server.sh smayaa.3-110-175-240.sslip.io
#
# Options (environment variables):
#   WEB_SERVER=caddy|nginx  default: nginx if nginx is already installed, else caddy.
#                           nginx adds one site and gets the certificate with certbot,
#                           leaving other nginx sites untouched.
#   API_PORT=8000           local port for the API (must be free; only reachable on 127.0.0.1)
#   e.g. sudo API_PORT=8010 bash setup-server.sh smayaa.43-239-93-107.sslip.io
#
# Result: PostgreSQL (local only), the API as a systemd service, HTTPS for the web app,
# and nightly database backups.
set -euo pipefail

HOST="${1:?usage: sudo bash setup-server.sh <hostname>}"
REPO_URL="https://github.com/MuskanKundu27/SMAYAA.git"
BASE=/opt/smayaa
APP="$BASE/app"          # git checkout (contains api/, web/, deploy/)
VENV="$BASE/venv"
WEB=/var/www/smayaa      # built web app, uploaded from a developer machine
BACKUPS=/var/backups/smayaa
DEPLOY_ENV="$BASE/deploy.env"   # choices made here, reused by update-api.sh

[ "$(id -u)" -eq 0 ] || { echo "Run with sudo."; exit 1; }
step() { echo; echo "==> $*"; }

# Earlier choices win, so re-running never silently switches web server or port.
# shellcheck disable=SC1090
[ -f "$DEPLOY_ENV" ] && . "$DEPLOY_ENV"
if [ -z "${WEB_SERVER:-}" ]; then
  if command -v nginx >/dev/null; then WEB_SERVER=nginx; else WEB_SERVER=caddy; fi
fi
API_PORT="${API_PORT:-8000}"
case "$WEB_SERVER" in caddy|nginx) ;; *) echo "WEB_SERVER must be caddy or nginx"; exit 1 ;; esac
echo "Host: $HOST   web server: $WEB_SERVER   API port: $API_PORT"

step "Check the API port is free (or already ours)"
if ss -ltnp "sport = :$API_PORT" | grep -q LISTEN \
   && ! systemctl is-active --quiet smayaa-api; then
  echo "Port $API_PORT is used by another program:"
  ss -ltnp "sport = :$API_PORT"
  echo "Choose another, e.g.: sudo API_PORT=8010 bash setup-server.sh $HOST"
  exit 1
fi

step "Swap file (1 GB) if the server has no swap at all"
if [ -z "$(swapon --show)" ]; then
  fallocate -l 1G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

step "System packages"
apt-get update -q
apt-get install -y -q git python3.12-venv curl
# Reuse an existing PostgreSQL server (we only add our own roles and database).
command -v psql >/dev/null || apt-get install -y -q postgresql

if [ "$WEB_SERVER" = caddy ]; then
  step "Caddy web server (official repository)"
  if ! command -v caddy >/dev/null; then
    apt-get install -y -q gpg debian-keyring debian-archive-keyring apt-transport-https
    curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key \
      | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt \
      > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -q
    apt-get install -y -q caddy
  fi
else
  step "certbot for nginx (free Let's Encrypt certificates)"
  apt-get install -y -q certbot python3-certbot-nginx
fi

step "Service account 'smayaa' (runs the API, owns the code)"
id smayaa >/dev/null 2>&1 || useradd --system --home-dir "$BASE" --shell /usr/sbin/nologin smayaa
mkdir -p "$BASE"
chown smayaa:smayaa "$BASE"
printf 'WEB_SERVER=%s\nAPI_PORT=%s\nHOST=%s\n' "$WEB_SERVER" "$API_PORT" "$HOST" > "$DEPLOY_ENV"

step "Code"
if [ ! -d "$APP/.git" ]; then
  sudo -u smayaa git clone -q "$REPO_URL" "$APP"
else
  sudo -u smayaa git -C "$APP" pull -q --ff-only
fi

step "Settings file $APP/.env (created once, never overwritten)"
if [ ! -f "$APP/.env" ]; then
  DB_PORT=$(sudo -u postgres psql -tAc 'SHOW port')
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
  # Subshell: the private umask applies to the secrets file only, not to later steps.
  (
    umask 077
    cat > "$APP/.env" <<ENV
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://smayaa_app:${APP_PW}@127.0.0.1:${DB_PORT}/smayaa
MIGRATION_DATABASE_URL=postgresql+psycopg://smayaa_owner:${OWNER_PW}@127.0.0.1:${DB_PORT}/smayaa
JWT_SECRET=$(openssl rand -hex 32)
CORS_ORIGINS=https://${HOST}
LOG_LEVEL=INFO
ENV
  )
  chown smayaa:smayaa "$APP/.env"
  chmod 600 "$APP/.env"
fi

step "Python environment and database migrations"
[ -d "$VENV" ] || sudo -u smayaa python3.12 -m venv "$VENV"
sudo -u smayaa "$VENV/bin/pip" install -q --upgrade pip
sudo -u smayaa "$VENV/bin/pip" install -q -e "$APP/api"
(cd "$APP/api" && sudo -u smayaa "$VENV/bin/alembic" upgrade head)

step "API service on 127.0.0.1:$API_PORT"
sed "s/__API_PORT__/$API_PORT/g" "$APP/deploy/smayaa-api.service" \
  > /etc/systemd/system/smayaa-api.service
chmod 644 /etc/systemd/system/smayaa-api.service
systemctl daemon-reload
systemctl enable --now smayaa-api
systemctl restart smayaa-api

step "Web folder $WEB (filled by deploy/push-web.ps1 from a developer machine)"
mkdir -p "$WEB"
chmod 755 "$(dirname "$WEB")" "$WEB"
[ -f "$WEB/index.html" ] || echo '<p>SMAYAA is being deployed. Upload the web app next.</p>' > "$WEB/index.html"
chmod 644 "$WEB/index.html"

if [ "$WEB_SERVER" = caddy ]; then
  step "Caddy site for https://$HOST"
  sed "s/__HOST__/$HOST/g" "$APP/deploy/Caddyfile" | sed "s/__API_PORT__/$API_PORT/g" \
    > /etc/caddy/Caddyfile
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
  # validate runs as root and may create the log file; Caddy itself runs as user "caddy".
  chown -R caddy:caddy /var/log/caddy
  systemctl reload caddy || systemctl restart caddy
else
  step "nginx site for https://$HOST (other sites are not changed)"
  SITE=/etc/nginx/sites-available/smayaa
  [ -f "$SITE" ] && cp "$SITE" "$SITE.bak"
  sed "s/__HOST__/$HOST/g" "$APP/deploy/nginx-smayaa.conf" | sed "s/__API_PORT__/$API_PORT/g" \
    > "$SITE"
  ln -sf "$SITE" /etc/nginx/sites-enabled/smayaa
  if ! nginx -t; then
    # Never leave nginx with a broken config: the other sites depend on it.
    rm -f /etc/nginx/sites-enabled/smayaa
    [ -f "$SITE.bak" ] && mv "$SITE.bak" "$SITE" && ln -sf "$SITE" /etc/nginx/sites-enabled/smayaa
    echo "nginx config test failed; SMAYAA site disabled, nothing else changed."
    exit 1
  fi
  systemctl reload nginx
  # Gets the certificate (or reuses a valid one), adds HTTPS + redirect to our site only.
  certbot --nginx -d "$HOST" --non-interactive --agree-tos --register-unsafely-without-email \
    --keep-until-expiring --redirect
fi

step "Nightly database backup (02:30 UTC, keeps 14 days, same server)"
mkdir -p "$BACKUPS"
chmod 700 "$BACKUPS"
install -m 755 "$APP/deploy/backup.sh" /usr/local/bin/smayaa-backup
echo '30 2 * * * root /usr/local/bin/smayaa-backup' > /etc/cron.d/smayaa-backup
chmod 644 /etc/cron.d/smayaa-backup

step "Done"
echo "Open https://$HOST (the certificate can take a minute on first visit)."
echo "Next: upload the web app (deploy/push-web.ps1), then create the platform admin:"
echo "  cd $APP/api && sudo -u smayaa $VENV/bin/python -m app.scripts.create_platform_admin"

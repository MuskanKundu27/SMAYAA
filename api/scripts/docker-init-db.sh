#!/bin/sh
# Runs once when the Docker Postgres volume is first created (docker-compose.yml).
set -e
psql -v ON_ERROR_STOP=1 -U postgres \
    -v owner_pw="$SMAYAA_OWNER_PW" -v app_pw="$SMAYAA_APP_PW" \
    -f /scripts/create_dev_db.sql

-- Creates the local development and test databases and their roles.
-- Run once as the PostgreSQL superuser:
--   psql -U postgres -h localhost -v owner_pw=... -v app_pw=... -f api/scripts/create_dev_db.sql
--
-- Two roles, on purpose:
--   smayaa_owner  owns the schema and runs Alembic migrations.
--   smayaa_app    used by the API at runtime. It does NOT own the tables, so
--                 Postgres row-level security applies to it (table owners bypass RLS).

\set ON_ERROR_STOP on

SELECT format('CREATE ROLE smayaa_owner LOGIN PASSWORD %L', :'owner_pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smayaa_owner') \gexec

SELECT format('CREATE ROLE smayaa_app LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD %L', :'app_pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smayaa_app') \gexec

SELECT 'CREATE DATABASE smayaa OWNER smayaa_owner'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'smayaa') \gexec

SELECT 'CREATE DATABASE smayaa_test OWNER smayaa_owner'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'smayaa_test') \gexec

\connect smayaa
\ir grant_app_role.sql

\connect smayaa_test
\ir grant_app_role.sql

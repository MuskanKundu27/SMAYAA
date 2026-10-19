-- Grants the runtime role access to everything the owner role creates in schema "public".
-- Included by create_dev_db.sql; also usable on its own against any SMAYAA database.

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO smayaa_owner;
GRANT USAGE ON SCHEMA public TO smayaa_app;

ALTER DEFAULT PRIVILEGES FOR ROLE smayaa_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO smayaa_app;
ALTER DEFAULT PRIVILEGES FOR ROLE smayaa_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO smayaa_app;

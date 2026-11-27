#!/usr/bin/env bash
set -euo pipefail

# Runs only when PostgreSQL initializes a new data volume.
for service in model file training provider chat runtime; do
    psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
        --set=ON_ERROR_STOP=1 \
        --set=role="${service}_user" --set=db="${service}_db" \
        --set=password="$APP_DB_PASSWORD" <<'SQL'
CREATE ROLE :"role" LOGIN PASSWORD :'password';
CREATE DATABASE :"db" OWNER :"role";
REVOKE CONNECT ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO :"role";
SQL
done

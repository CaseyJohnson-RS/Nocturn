#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
  CREATE DATABASE auth OWNER auth_user;
  CREATE DATABASE notes OWNER notes_user;
EOSQL

#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
  CREATE DATABASE auth_local OWNER auth_user;
  CREATE DATABASE auth_dev OWNER auth_user;
  CREATE DATABASE auth_test OWNER auth_user;
  
  CREATE DATABASE notes_local OWNER notes_user;
  CREATE DATABASE notes_dev OWNER notes_user;
  CREATE DATABASE notes_test OWNER notes_user;
EOSQL

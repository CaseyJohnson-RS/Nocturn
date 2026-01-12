# PostgreSQL Infrastructure

This directory contains the infrastructure setup for PostgreSQL databases used in the Nocturn project. It includes Docker Compose configuration for running PostgreSQL instances for development and testing environments, along with initialization scripts to create necessary roles and databases.

## Overview

The setup provides two main databases:
- `auth`: For the authentication service
- `notes`: For the notes service

Each database has its own dedicated user with appropriate permissions.

## Prerequisites

- Docker and Docker Compose installed
- Make utility (for using the Makefile commands)

## Configuration

1. Copy the example environment file:
   ```bash
   cp .env.db.example .env.db
   ```

2. Edit `.env.db` to set your desired passwords and configuration.

The environment file contains:
- `POSTGRES_USER`: Admin user for PostgreSQL
- `POSTGRES_PASSWORD`: Password for the admin user
- `AUTH_DB_USER`: User for the auth database
- `AUTH_DB_PASSWORD`: Password for the auth database user
- `NOTES_DB_USER`: User for the notes database
- `NOTES_DB_PASSWORD`: Password for the notes database user

## Usage

### Development Environment

To start the development PostgreSQL instance:
```bash
make dev-up
```

To stop it:
```bash
make dev-down
```

The development instance runs on port 5432 and uses example environment variables.

### Test Environment

To start the test PostgreSQL instance:
```bash
make test-up
```

To stop it (including removing volumes):
```bash
make test-down
```

The test instance runs on port 5433 and uses example environment variables.

### Help

To see all available commands:
```bash
make help
```

## Initialization

When the container starts for the first time, the initialization scripts in the `init/` directory will:
1. Create the necessary database roles/users
2. Create the `auth` and `notes` databases with appropriate ownership

## Data Persistence

Database data is persisted in Docker volumes:
- `dev_postgres_data` for the development environment
- `test_postgres_data` for the test environment

## Connecting to the Database

Once running, you can connect to the databases using:
- Host: `localhost`
- Port: `5432` (dev) or `5433` (test)
- Database: `auth` or `notes`
- User: `auth_admin` or `notes_admin` (as defined in your `.env.db`)

Example connection string:
```
postgresql://auth_admin:password@localhost:5432/auth
```

## Files

- `docker-compose.yaml`: Docker Compose configuration
- `Makefile`: Convenience commands for managing environments
- `.env.db.example`: Example environment file
- `init/01_create_roles.sh`: Script to create database roles
- `init/02_create_dbs.sh`: Script to create databases

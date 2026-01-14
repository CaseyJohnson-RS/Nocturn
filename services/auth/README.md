# Auth Service

## Description

This is an authentication service built with FastAPI that provides JWT token issuance for other services. It includes features such as user registration, email verification, password reset, security event tracking, and more.

## Features

- User registration with email verification
- Password hashing with bcrypt
- Email verification tokens
- Password reset functionality
- Refresh tokens
- Security event logging
- PostgreSQL database with async support
- Alembic migrations

## Prerequisites

- Python 3.10+
- uv package manager
- Docker and Docker Compose (for database)

## Installation

1. Clone the repository and navigate to the project directory.

2. Install `uv` if not already installed:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Sync the environment:
   ```bash
   uv sync
   ```

4. Copy the environment file and configure it:
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

## Database Setup

1. Start the PostgreSQL database using Docker Compose:
   ```bash
   make db-up ENV_FILE=.env
   ```

2. Run migrations:
   ```bash
   make migrate ENV_FILE=.env
   ```

## Running the Application

### Running Locally

1. Activate the virtual environment:
   ```bash
   source .venv/bin/activate  # Linux/macOS
   # or
   .venv\Scripts\activate     # Windows
   ```

2. Run the ASGI server:
   ```bash
   uvicorn app.main:app --host localhost --port 8000 --reload
   ```

   Or using uv:
   ```bash
   uv run uvicorn app.main:app --host localhost --port 8000 --reload --env-file .env
   ```

   Or using Makefile:
   ```bash
   make run ENV_FILE=.env
   ```

### Running in Docker

1. Build and run the service in a container:
   ```bash
   docker build -t auth-service .
   docker run -p 8000:8000 --env-file .env auth-service
   ```

## Project Structure

- `app/main.py` - FastAPI application entry point
- `app/routers/` - API routers
- `app/services/` - Business logic services
- `app/models/` - SQLAlchemy models
- `app/schemas/` - Pydantic schemas
- `app/core/` - Core settings and configurations
- `migrations/` - Alembic migration files
- `tests/` - Test files

## Contributing

1. Create a feature branch
2. Make your changes
3. Run migrations if database schema changed
4. Test your changes
5. Submit a pull request

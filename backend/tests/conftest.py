import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://nocturn:nocturn_test@localhost:5433/nocturn_test"
os.environ["REDIS_URL"] = "redis://localhost:6380/0"
os.environ["JWT_SECRET"] = "test-secret-key-at-least-32-characters-long"
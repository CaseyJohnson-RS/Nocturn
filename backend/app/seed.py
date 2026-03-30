import logging

from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.modules.auth.models import User

logger = logging.getLogger(__name__)
ph = PasswordHasher()


async def seed_admin(db: AsyncSession) -> None:
    if not settings.admin_email or not settings.admin_password:
        logger.info("Admin seed skipped: ADMIN_EMAIL or ADMIN_PASSWORD not set")
        return

    result = await db.execute(select(User).where(User.role == "admin").limit(1))
    if result.scalar_one_or_none():
        logger.info("Admin already exists, skipping seed")
        return

    admin = User(
        email=settings.admin_email.lower(),
        nickname=settings.admin_nickname,
        password_hash=ph.hash(settings.admin_password),
        role="admin",
        is_email_confirmed=True,
    )
    db.add(admin)
    await db.commit()
    logger.info("Admin user created: %s", settings.admin_email)

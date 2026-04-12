import asyncio
import logging
import time

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker")

engine = create_async_engine(settings.database_url, pool_size=5)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def run_embedding_queue():
    """Process pending embedding tasks."""
    from app.modules.rag.repository import RAGRepository
    from app.modules.rag.service import RAGService

    async with session_factory() as session:
        repo = RAGRepository(session)
        tasks = await repo.get_pending_tasks(limit=20)

    if not tasks:
        return

    logger.info("Processing %d embedding tasks", len(tasks))

    for task in tasks:
        async with session_factory() as session:
            repo = RAGRepository(session)
            await repo.mark_processing(task.id)
            await session.commit()

            try:
                service = RAGService(session)
                await service.embed_note_chunks(task.note_id)  # type: ignore
                await repo.mark_done(task.id)
                await session.commit()
                logger.info("Embedded note %s", task.note_id)
            except Exception as e:
                await session.rollback()
                logger.error("Failed to embed note %s: %s", task.note_id, e)
                async with session_factory() as err_session:
                    err_repo = RAGRepository(err_session)
                    await err_repo.mark_failed(task.id, str(e), task.attempts + 1)
                    await err_session.commit()


async def run_cleanup():
    """Run all periodic cleanup tasks."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete, select

    from app.modules.ai.models import ChatSession
    from app.modules.auth.models import RefreshToken, User, VerificationToken
    from app.modules.notes.models import Note

    now = datetime.now(UTC)

    async with session_factory() as session:
        # 1. Purge expired trashed notes
        trash_cutoff = now - timedelta(days=settings.trash_retention_days)
        result = await session.execute(
            select(Note).where(
                Note.deleted_at.is_not(None),
                Note.deleted_at < trash_cutoff,
            )
        )
        expired_notes = result.scalars().all()

        if expired_notes:
            logger.info("Purging %d expired trashed notes", len(expired_notes))
            from app.modules.rag.repository import RAGRepository

            repo = RAGRepository(session)
            for note in expired_notes:
                await repo.delete_chunks_for_note(note.id)
                await repo.remove_task(note.id)

            await session.execute(
                delete(Note).where(
                    Note.deleted_at.is_not(None),
                    Note.deleted_at < trash_cutoff,
                )
            )

        # 2. Purge expired refresh tokens
        result = await session.execute(delete(RefreshToken).where(RefreshToken.expires_at < now))
        if result.rowcount:  # type: ignore
            logger.info("Purged %d expired refresh tokens", result.rowcount)  # type: ignore

        # 3. Purge expired verification tokens
        result = await session.execute(
            delete(VerificationToken).where(VerificationToken.expires_at < now)
        )
        if result.rowcount:  # type: ignore
            logger.info("Purged %d expired verification tokens", result.rowcount)  # type: ignore

        # 4. Purge stale unconfirmed accounts
        unconfirmed_cutoff = now - timedelta(hours=settings.unconfirmed_account_ttl_hours)
        result = await session.execute(
            delete(User).where(
                User.is_email_confirmed.is_(False),
                User.created_at < unconfirmed_cutoff,
            )
        )
        if result.rowcount:  # type: ignore
            logger.info("Purged %d stale unconfirmed accounts", result.rowcount)  # type: ignore

        # 5. Purge expired chat sessions
        session_cutoff = now - timedelta(days=settings.chat_session_ttl_days)
        result = await session.execute(
            delete(ChatSession).where(ChatSession.updated_at < session_cutoff)  # type: ignore
        )
        if result.rowcount:  # type: ignore
            logger.info("Purged %d expired chat sessions", result.rowcount)  # type: ignore

        await session.commit()


async def main():
    logger.info("Worker started")

    embedding_interval = settings.embedding_queue_interval_seconds
    cleanup_interval = settings.cleanup_interval_seconds
    last_cleanup = time.monotonic()

    while True:
        try:
            await run_embedding_queue()
        except Exception as e:
            logger.error("Embedding queue error: %s", e)

        now = time.monotonic()
        if now - last_cleanup >= cleanup_interval:
            try:
                await run_cleanup()
            except Exception as e:
                logger.error("Cleanup error: %s", e)
            last_cleanup = now

        await asyncio.sleep(embedding_interval)


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import logging

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
            await repo.mark_processing(task.id)
            await session.commit()

            try:
                service = RAGService(session)
                await service.embed_note_chunks(task.note_id)
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
    """Run cleanup tasks: purge old soft-deleted notes past retention."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete, select

    from app.modules.notes.models import Note

    cutoff = datetime.now(UTC) - timedelta(days=settings.trash_retention_days)

    async with session_factory() as session:
        result = await session.execute(
            select(Note).where(
                Note.deleted_at.is_not(None),
                Note.deleted_at < cutoff,
            )
        )
        expired = result.scalars().all()

        if not expired:
            return

        logger.info("Purging %d expired trashed notes", len(expired))

        from app.modules.rag.repository import RAGRepository

        repo = RAGRepository(session)
        for note in expired:
            await repo.delete_chunks_for_note(note.id)
            await repo.remove_task(note.id)

        await session.execute(
            delete(Note).where(
                Note.deleted_at.is_not(None),
                Note.deleted_at < cutoff,
            )
        )
        await session.commit()


async def main():
    logger.info("Worker started")

    embedding_interval = settings.embedding_queue_interval_seconds
    cleanup_interval = settings.cleanup_interval_seconds
    last_cleanup = 0.0
    elapsed = 0.0

    while True:
        try:
            await run_embedding_queue()
        except Exception as e:
            logger.error("Embedding queue error: %s", e)

        if elapsed - last_cleanup >= cleanup_interval:
            try:
                await run_cleanup()
            except Exception as e:
                logger.error("Cleanup error: %s", e)
            last_cleanup = elapsed

        await asyncio.sleep(embedding_interval)
        elapsed += embedding_interval


if __name__ == "__main__":
    asyncio.run(main())

"""Background worker: embedding queue + periodic cleanup.

Instrumented for Prometheus on its own port (the worker has no HTTP server of
its own, so ``prometheus_client.start_http_server`` provides one) and logs in
the same JSON format as the API so both streams land in one Loki view.
"""

import asyncio
import contextlib
import logging
import os
import signal
import time

from prometheus_client import start_http_server
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.app.common import models  # type: ignore # noqa: F401
from src.app.common.observability.logging import setup_logging
from src.app.common.observability.metrics import (
    embedding_queue_oldest_pending_seconds,
    embedding_queue_tasks,
    embedding_task_duration_seconds,
    embedding_tasks_total,
    set_build_info,
    worker_cleanup_deleted_total,
    worker_last_loop_timestamp_seconds,
    worker_loop_iterations_total,
)
from src.app.config import settings

setup_logging("worker")
logger = logging.getLogger("worker")

engine = create_async_engine(settings.database_url, pool_size=5, pool_pre_ping=True)
session_factory = async_sessionmaker(engine, expire_on_commit=False)

_shutdown = asyncio.Event()

# A task left in `processing` by a worker that died mid-flight would never be
# retried. Anything older than this is handed back to the queue.
STUCK_TASK_MINUTES = 15


async def refresh_queue_metrics() -> None:
    """Publish queue depth per status and the age of the oldest pending task.

    The oldest-pending age is the freshness SLI: it answers "how long after a
    save does a note become searchable" without per-note tracing.
    """
    from src.app.modules.rag.models import EmbeddingTask

    async with session_factory() as session:
        rows = await session.execute(
            select(EmbeddingTask.status, func.count()).group_by(EmbeddingTask.status)
        )
        counts = dict(rows.all())

        # Always publish every status: if a series disappears when the queue
        # drains, alerts see a gap instead of a zero.
        for status in ("pending", "processing", "failed"):
            embedding_queue_tasks.labels(status=status).set(counts.get(status, 0))

        oldest = await session.execute(
            select(func.min(EmbeddingTask.updated_at)).where(EmbeddingTask.status == "pending")
        )
        oldest_at = oldest.scalar_one_or_none()
        if oldest_at is None:
            embedding_queue_oldest_pending_seconds.set(0)
        else:
            # Compare against the database clock, not the worker's.
            now = await session.scalar(text("SELECT now()"))
            embedding_queue_oldest_pending_seconds.set(max(0.0, (now - oldest_at).total_seconds()))


async def requeue_stuck_tasks() -> None:
    """Return tasks abandoned by a crashed worker to the pending state."""
    async with session_factory() as session:
        result = await session.execute(
            text(
                "UPDATE embedding_queue SET status = 'pending' "
                "WHERE status = 'processing' "
                "AND updated_at < now() - make_interval(mins => :mins)"
            ),
            {"mins": STUCK_TASK_MINUTES},
        )
        await session.commit()
        count = result.rowcount  # type: ignore[union-attr]
        if count:
            logger.warning("Requeued stuck embedding tasks", extra={"count": count})
            embedding_tasks_total.labels(outcome="requeued").inc(count)


async def run_embedding_queue():
    """Process pending embedding tasks."""
    from src.app.modules.rag.repository import RAGRepository
    from src.app.modules.rag.service import RAGService

    async with session_factory() as session:
        repo = RAGRepository(session)
        tasks = await repo.get_pending_tasks(limit=20)

    if not tasks:
        return

    logger.info("Processing embedding tasks", extra={"count": len(tasks)})

    for task in tasks:
        async with session_factory() as session:
            repo = RAGRepository(session)
            await repo.mark_processing(task.id)
            await session.commit()

            started = time.perf_counter()
            try:
                service = RAGService(session)
                await service.embed_note(task.note_id, task.user_id)

                await repo.mark_done(task.id)
                await session.commit()

                embedding_task_duration_seconds.observe(time.perf_counter() - started)
                embedding_tasks_total.labels(outcome="success").inc()
                logger.info("Embedded note", extra={"note_id": str(task.note_id)})

            except Exception as e:
                await session.rollback()
                embedding_task_duration_seconds.observe(time.perf_counter() - started)
                embedding_tasks_total.labels(outcome="error").inc()
                logger.error(
                    "Failed to embed note",
                    extra={"note_id": str(task.note_id), "error": str(e)},
                )

                async with session_factory() as err_session:
                    err_repo = RAGRepository(err_session)
                    await err_repo.mark_failed(task.id, str(e), task.attempts + 1)
                    await err_session.commit()


async def run_cleanup():
    """Run all periodic cleanup tasks."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete

    from src.app.modules.ai.models import ChatSession
    from src.app.modules.auth.models import RefreshToken, User, VerificationToken
    from src.app.modules.notes.models import Note

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
            logger.info("Purging expired trashed notes", extra={"count": len(expired_notes)})
            from src.app.modules.rag.repository import RAGRepository

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
            worker_cleanup_deleted_total.labels(kind="trashed_notes").inc(len(expired_notes))

        # 2. Purge expired refresh tokens
        result = await session.execute(delete(RefreshToken).where(RefreshToken.expires_at < now))
        if result.rowcount:  # type: ignore
            logger.info("Purged expired refresh tokens", extra={"count": result.rowcount})  # type: ignore
            worker_cleanup_deleted_total.labels(kind="refresh_tokens").inc(result.rowcount)  # type: ignore

        # 3. Purge expired verification tokens
        result = await session.execute(
            delete(VerificationToken).where(VerificationToken.expires_at < now)
        )
        if result.rowcount:  # type: ignore
            logger.info("Purged expired verification tokens", extra={"count": result.rowcount})  # type: ignore
            worker_cleanup_deleted_total.labels(kind="verification_tokens").inc(result.rowcount)  # type: ignore

        # 4. Purge stale unconfirmed accounts
        unconfirmed_cutoff = now - timedelta(hours=settings.unconfirmed_account_ttl_hours)
        result = await session.execute(
            delete(User).where(
                User.is_email_confirmed.is_(False),
                User.created_at < unconfirmed_cutoff,
            )
        )
        if result.rowcount:  # type: ignore
            logger.info("Purged stale unconfirmed accounts", extra={"count": result.rowcount})  # type: ignore
            worker_cleanup_deleted_total.labels(kind="unconfirmed_accounts").inc(result.rowcount)  # type: ignore

        # 5. Purge expired chat sessions
        session_cutoff = now - timedelta(days=settings.chat_session_ttl_days)
        result = await session.execute(
            delete(ChatSession).where(ChatSession.updated_at < session_cutoff)  # type: ignore
        )
        if result.rowcount:  # type: ignore
            logger.info("Purged expired chat sessions", extra={"count": result.rowcount})  # type: ignore
            worker_cleanup_deleted_total.labels(kind="chat_sessions").inc(result.rowcount)  # type: ignore

        await session.commit()


def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    """Stop at the end of the current iteration instead of dying mid-task."""
    for sig in (signal.SIGTERM, signal.SIGINT):
        # add_signal_handler is not implemented on Windows.
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _shutdown.set)


async def main():
    set_build_info(service="worker", version="0.1.0", commit=os.getenv("GIT_COMMIT", "unknown"))
    start_http_server(settings.worker_metrics_port)
    _install_signal_handlers(asyncio.get_running_loop())

    logger.info("Worker started", extra={"metrics_port": settings.worker_metrics_port})

    embedding_interval = settings.embedding_queue_interval_seconds
    cleanup_interval = settings.cleanup_interval_seconds
    last_cleanup = time.monotonic()

    while not _shutdown.is_set():
        for name, step in (
            ("requeue_stuck", requeue_stuck_tasks),
            ("embedding_queue", run_embedding_queue),
            ("queue_metrics", refresh_queue_metrics),
        ):
            try:
                await step()
            except Exception as e:
                logger.error("Worker step failed", extra={"step": name, "error": str(e)})

        now = time.monotonic()
        if now - last_cleanup >= cleanup_interval:
            try:
                await run_cleanup()
            except Exception as e:
                logger.error("Cleanup error", extra={"error": str(e)})
            last_cleanup = now

        worker_loop_iterations_total.inc()
        worker_last_loop_timestamp_seconds.set(time.time())

        # Wake early on SIGTERM so shutdown is not held hostage by the interval.
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(_shutdown.wait(), timeout=embedding_interval)

    logger.info("Worker shutting down")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

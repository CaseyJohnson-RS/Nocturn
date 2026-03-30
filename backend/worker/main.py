import asyncio
import logging

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker")


async def run_embedding_queue():
    """Process pending embedding tasks."""
    logger.info("Processing embedding queue...")
    # Will be implemented in Phase 4


async def run_cleanup():
    """Run all cleanup tasks."""
    logger.info("Running cleanup tasks...")
    # Will be implemented in Phase 4


async def main():
    logger.info("Worker started")

    while True:
        tasks = [
            run_embedding_queue(),
            run_cleanup(),
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.sleep(settings.embedding_queue_interval_seconds)


if __name__ == "__main__":
    asyncio.run(main())

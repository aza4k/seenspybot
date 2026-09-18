import asyncio
import logging
import sys
from main import main as run_bot
from ttl_saver import main as run_ttl_saver
from scheduler import run_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Runner")


async def start_all():
    logger.info("🚀 Tizimlar ishga tushmoqda...")
    try:
        tasks = [run_bot(), run_scheduler()]
        from pathlib import Path
        if Path("user_session.session").exists():
            tasks.append(run_ttl_saver())
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Tizim to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(start_all())
    except (KeyboardInterrupt, SystemExit):
        logger.info("To'xtatildi.")

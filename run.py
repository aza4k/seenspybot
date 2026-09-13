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
    logger.info("🚀 Barcha tizimlar (Bot + TTL Saver + Scheduler) parallel ishga tushmoqda...")
    try:
        await asyncio.gather(
            run_bot(),
            run_ttl_saver(),
            run_scheduler()
        )
    except (KeyboardInterrupt, SystemExit):
        logger.info("Tizim to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(start_all())
    except (KeyboardInterrupt, SystemExit):
        logger.info("To'xtatildi.")

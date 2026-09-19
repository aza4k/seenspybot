import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import init_db
from handlers import admin_router, common_router, business_router, payments_router

# Log tizimini sozlash
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


async def main():
    if not BOT_TOKEN:
        logger.error(
            "XATOLIK: BOT_TOKEN ko'rsatilmagan! Iltimos, .env faylini yarating va BOT_TOKEN o'zgaruvchisini kiriting."
        )
        sys.exit(1)

    # Ma'lumotlar bazasini initsializatsiya qilish
    logger.info("Ma'lumotlar bazasi tayyorlanmoqda...")
    await init_db()

    # Bot va Dispatcher yaratish
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Routerlarni ulash
    dp.include_routers(admin_router, common_router, business_router, payments_router)

    # Bot buyruqlari menyusini o'rnatish (/start va /buy)
    try:
        from aiogram.types import BotCommand, BotCommandScopeDefault
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Bosh menyu / Главное меню"),
                BotCommand(command="buy", description="Tariflar / Тарифы"),
            ],
            scope=BotCommandScopeDefault()
        )
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Bosh menyu"),
                BotCommand(command="buy", description="Tariflar"),
            ],
            language_code="uz"
        )
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Главное меню"),
                BotCommand(command="buy", description="Тарифы"),
            ],
            language_code="ru"
        )
        logger.info("Bot buyruqlari muvaffaqiyatli o'rnatildi (/start, /buy).")
    except Exception as e:
        logger.warning(f"Bot buyruqlarini o'rnatishda xatolik: {e}")

    # Botni ishga tushirish (Business update'larni qamrab olgan holda)
    allowed_updates = dp.resolve_used_update_types()
    logger.info(f"Bot ishga tushmoqda. Qabul qilinadigan hodisalar: {allowed_updates}")

    try:
        # Eski o'qilmagan xabarlarni o'tkazib yuborish (ixtiyoriy)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=allowed_updates)
    finally:
        from database import close_db
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")

import asyncio
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import (
    get_unnotified_expired_users,
    mark_expired_notified,
    get_unnotified_cutoff_users,
    mark_cutoff_notified,
    get_user_language,
)
from config import BOT_TOKEN
from locales import get_text

logger = logging.getLogger("Scheduler")


async def run_scheduler(bot: Bot = None):
    """Obunasi tugagan foydalanuvchilarni vaqtida ogohlantirish vazifasi."""
    should_close_bot = False
    if not bot:
        bot = Bot(token=BOT_TOKEN)
        should_close_bot = True

    logger.info("⏰ Obunalar monitoringi (Scheduler) ishga tushdi.")

    try:
        while True:
            try:
                # 1. Obunasi endi tugagan foydalanuvchilarni tekshirish
                expired_users = await get_unnotified_expired_users()
                for item in expired_users:
                    user_id = item["user_id"]
                    exp_date = item.get("expires_at", "")
                    lang = await get_user_language(user_id)
                    kb = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text=get_text("btn_renew_sub", lang), callback_data="show_plans")]
                        ]
                    )
                    msg = get_text("scheduler_expired", lang, exp_date=exp_date)
                    try:
                        await bot.send_message(user_id, msg, reply_markup=kb, parse_mode="HTML")
                        await mark_expired_notified(user_id)
                        logger.info(f"🔔 User {user_id} ga obuna tugagani haqida ogohlantirish yuborildi.")
                    except Exception as e:
                        logger.error(f"User {user_id} ga bildirishnoma yuborishda xatolik: {e}")

                # 2. Obunasi tugaganiga 30 kundan oshgan foydalanuvchilarni tekshirish (Cutoff)
                cutoff_users = await get_unnotified_cutoff_users()
                for item in cutoff_users:
                    user_id = item["user_id"]
                    lang = await get_user_language(user_id)
                    kb = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text=get_text("btn_renew_sub", lang), callback_data="show_plans")]
                        ]
                    )
                    cutoff_msg = get_text("scheduler_cutoff", lang)
                    try:
                        await bot.send_message(user_id, cutoff_msg, reply_markup=kb, parse_mode="HTML")
                        await mark_cutoff_notified(user_id)
                        logger.info(f"🚫 User {user_id} ga 30 kunlik to'xtatish haqida ogohlantirish yuborildi.")
                    except Exception as e:
                        logger.error(f"User {user_id} ga cutoff bildirishnoma yuborishda xatolik: {e}")

            except Exception as e:
                logger.error(f"Scheduler siklida xatolik: {e}")

            # Har 10 daqiqada tekshirish (600 soniya)
            await asyncio.sleep(600)
    finally:
        if should_close_bot:
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run_scheduler())

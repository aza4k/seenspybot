import os
import sys
import logging
import asyncio
from pathlib import Path
from typing import Any, Optional
from telethon import TelegramClient, events
from aiogram import Bot
from aiogram.types import FSInputFile
from dotenv import load_dotenv

# UTF-8 konsol
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", 0))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8423213791"))

from config import ADMIN_ID, ARCHIVE_CHANNEL_ID
from database import (
    get_user_subscription_status,
    save_archive_log,
    count_undelivered_messages,
    get_user_language,
)
from locales import get_text

MEDIA_DIR = Path("media_cache")
MEDIA_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("ttl_saver.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("TTL_Saver")

# Telethon mijoz va Aiogram Bot
client = TelegramClient("user_session", API_ID, API_HASH)
bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
CURRENT_OWNER_ID = ADMIN_ID


async def send_media_to_chat(target_chat_id: int, file_path: str, caption: str, event_media: Any):
    """Media faylni belgilangan chat yoki kanalga yuborish."""
    if not bot:
        return None
    input_file = FSInputFile(file_path)
    doc = getattr(event_media, "document", None)
    is_voice = getattr(doc, "voice", False) or getattr(event_media, "voice", False)
    is_round = getattr(doc, "round", False) or getattr(event_media, "round", False)
    is_video = getattr(doc, "video", False) or getattr(event_media, "video", False)

    try:
        if is_voice:
            msg = await bot.send_voice(target_chat_id, voice=input_file, caption=caption, parse_mode="HTML")
        elif is_round:
            await bot.send_message(target_chat_id, caption, parse_mode="HTML")
            msg = await bot.send_video_note(target_chat_id, video_note=input_file)
        elif is_video:
            msg = await bot.send_video(target_chat_id, video=input_file, caption=caption, parse_mode="HTML")
        else:
            msg = await bot.send_photo(target_chat_id, photo=input_file, caption=caption, parse_mode="HTML")
        return msg.message_id
    except Exception as e:
        logger.error(f"Xabar yuborishda xatolik (chat={target_chat_id}): {e}")
        return None


@client.on(events.NewMessage(incoming=True))
async def on_new_message(event: events.NewMessage.Event):
    """1 martalik (View-Once / TTL) xabarlarni tutib, kanalga arxivlash va bot chatiga yuborish."""
    if not event.is_private:
        return

    if event.media:
        ttl = getattr(event.media, "ttl_seconds", None)
        if ttl is None:
            ttl = getattr(event.message, "ttl_period", None)

        if ttl is not None:
            sender = await event.get_sender()
            sender_name = getattr(sender, "first_name", "") or "Noma'lum"
            if getattr(sender, "last_name", None):
                sender_name += f" {sender.last_name}"
            if getattr(sender, "username", None):
                sender_name += f" (@{sender.username})"

            logger.info(f"🔥 1 martalik media tutildi! Kimdan: {sender_name}, TTL: {ttl}s")

            # Diskka yuklab olish
            file_path = await client.download_media(event.message, file=MEDIA_DIR)
            if not file_path or not bot:
                return

            owner_id = CURRENT_OWNER_ID or ADMIN_ID
            sub_status = await get_user_subscription_status(owner_id, ADMIN_ID)
            is_active = sub_status["is_active"]
            days_since_expiry = sub_status["days_since_expiry"]

            # 30 kundan oshgan bo'lsa, saqlamaymiz
            if days_since_expiry > 30:
                logger.warning(f"User {owner_id} obunasiz 30 kundan oshgan ({days_since_expiry} kun). TTL arxivlanmadi.")
                return

            ttl_display = "1 marta ko'rish" if ttl > 100000 else f"{ttl} soniya"
            time_str = event.date.strftime('%H:%M:%S')

            # 1. Shaxsiy arxiv kanaliga jo'natish
            channel_msg_id = None
            if ARCHIVE_CHANNEL_ID:
                channel_caption = (
                    f"#ARCHIVE #UID_{owner_id} #VIEW_ONCE\n"
                    "👁 <b>1 martalik media saqlandi!</b>\n\n"
                    f"👤 <b>Kimdan:</b> {sender_name}\n"
                    f"⏱ <b>Muddati:</b> {ttl_display}\n"
                    f"🕒 <b>Kelgan vaqti:</b> {time_str}"
                )
                channel_msg_id = await send_media_to_chat(
                    target_chat_id=ARCHIVE_CHANNEL_ID,
                    file_path=file_path,
                    caption=channel_caption,
                    event_media=event.media
                )

            # 2. Arxiv logiga yozish
            if channel_msg_id and owner_id:
                await save_archive_log(
                    user_id=owner_id,
                    chat_id=event.chat_id,
                    channel_msg_id=channel_msg_id,
                    event_type="view_once",
                    is_delivered=is_active
                )

            # 3. Foydalanuvchiga yetkazish yoki Teaser yuborish
            lang = await get_user_language(owner_id)
            if is_active and owner_id:
                caption = get_text(
                    "msg_view_once",
                    lang,
                    sender_name=sender_name,
                    chat_title="Личные сообщения" if lang == "ru" else "Shaxsiy chat",
                    time_str=time_str
                )
                await send_media_to_chat(
                    target_chat_id=owner_id,
                    file_path=file_path,
                    caption=caption,
                    event_media=event.media
                )
                logger.info(f"✅ 1 martalik media BOT chatiga yetkazildi: {file_path}")
            elif owner_id:
                # Obuna yo'q - teaser yuborish
                total_missed = await count_undelivered_messages(owner_id)
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text=get_text("btn_unlock", lang, total_missed=total_missed), callback_data="show_plans")]
                    ]
                )
                teaser_msg = get_text("teaser_view_once", lang, total_missed=total_missed)
                try:
                    await bot.send_message(owner_id, teaser_msg, reply_markup=kb, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"Teaser yuborishda xatolik: {e}")


async def main():
    global CURRENT_OWNER_ID
    if not API_ID or not API_HASH:
        logger.warning("⚠️ TELEGRAM_API_ID yoki TELEGRAM_API_HASH kiritilmagan. TTL Saver (MTProto) o'tkazib yuborildi.")
        return

    session_file = Path("user_session.session")
    if not session_file.exists():
        logger.warning("⚠️ user_session.session fayli topilmadi. TTL Saver (MTProto) o'tkazib yuborildi. Bot API to'liq rejimda ishlamoqda.")
        return

    logger.info("TTL Saver ishga tushmoqda...")
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.warning("⚠️ Telethon sessiyasi avtorizatsiyadan o'tmagan. TTL Saver o'tkazib yuborildi.")
            return

        me = await client.get_me()
        CURRENT_OWNER_ID = me.id
        logger.info(f"✅ Ulangan akkaunt: {me.first_name} (ID: {me.id})")
        logger.info("🎯 Barcha 1 martalik xabarlar @seenspybot botiga va kanalga arxivlanadi!")
        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"TTL Saver ishga tushishida xatolik: {e}")


if __name__ == "__main__":
    if API_ID and API_HASH and BOT_TOKEN:
        asyncio.run(main())
    else:
        logger.error("API_ID, API_HASH yoki BOT_TOKEN yetarli emas!")

import os
import html
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Any

from aiogram import Router, Bot, types
from aiogram.types import FSInputFile

from config import ADMIN_ID, ARCHIVE_CHANNEL_ID

UZB_TZ = timezone(timedelta(hours=5))

def format_time_utc5(time_val: Any, time_only: bool = False) -> str:
    """
    Vaqtni aniq O'zbekiston / Toshkent vaqti (UTC+5) ga o'tkazish.
    time_only=True bo'lsa faqat 'HH:MM:SS', False bo'lsa 'YYYY-MM-DD HH:MM:SS' qaytaradi.
    Bazada allaqachon Toshkent vaqti bilan saqlangan bo'lsa ham qayta +5 soat qo'shmasdan to'g'ri ko'rsatadi.
    """
    fmt = "%H:%M:%S" if time_only else "%Y-%m-%d %H:%M:%S"
    if not time_val:
        return datetime.now(UZB_TZ).strftime(fmt)

    if isinstance(time_val, str):
        try:
            clean_str = time_val.replace("T", " ")[:19]
            dt = datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S")
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            # Agar sana hozirgi UTC vaqtidan 10 daqiqadan ko'proq oldinda bo'lsa,
            # demak u bazada allaqachon Toshkent vaqti (UTC+5) bilan yozilgan!
            # Uni qayta +5 soatga surmaymiz.
            if dt > now_utc + timedelta(minutes=10):
                if time_only:
                    return dt.strftime("%H:%M:%S")
                return clean_str
            # Aks holda bu toza UTC vaqt, unga +5 soat qo'shamiz:
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(UZB_TZ).strftime(fmt)
        except Exception:
            return time_val
    elif isinstance(time_val, datetime):
        dt = time_val if time_val.tzinfo else time_val.replace(tzinfo=timezone.utc)
        return dt.astimezone(UZB_TZ).strftime(fmt)

    return str(time_val)
from database import (
    save_connection,
    get_connection_owner_chat,
    save_message,
    get_message,
    update_message_text,
    update_message_file_path,
    is_subscription_active,
    get_user_subscription_status,
    save_archive_log,
    count_undelivered_messages,
    ensure_free_trial,
    is_media_already_captured,
    mark_media_as_captured,
    get_user_language,
    process_referral_connection_reward,
)
from locales import get_text

logger = logging.getLogger(__name__)
router = Router(name="business_router")

MEDIA_DIR = Path("media_cache")
MEDIA_DIR.mkdir(exist_ok=True)


async def resolve_owner_chat_id(bot: Bot, connection_id: Optional[str]) -> Optional[int]:
    """Ulanish egasining chat_id sini bazadan yoki Telegram API orqali aniqlash."""
    if not connection_id:
        return None

    owner_chat = await get_connection_owner_chat(connection_id)
    if owner_chat:
        return owner_chat

    try:
        conn = await bot.get_business_connection(connection_id)
        if conn:
            await save_connection(conn.id, conn.user.id, conn.user_chat_id, conn.is_enabled)
            return conn.user_chat_id
    except Exception as e:
        logger.error(f"Telegram API dan ulanishni olishda xatolik: {e}")

    return None


def safe_build_text_message(
    header_info: str,
    text_content: str,
    promo_footer: str,
    msg_label: str = "Xabar",
    max_len: int = 4000
) -> str:
    """
    4096 belgidan oshib ketmasligi uchun xabar matnini xavfsiz qirqish va HTML teglarini to'liq yopish.
    """
    prefix = f"{header_info}💬 <b>{msg_label}:</b>\n<blockquote>"
    suffix = f"</blockquote>{promo_footer}"
    base_len = len(prefix) + len(suffix)
    available = max(50, max_len - base_len - 3)

    if len(text_content) > available:
        text_content = text_content[:available] + "..."

    return f"{prefix}{html.escape(text_content)}{suffix}"


def safe_build_caption(
    header_info: str,
    text_content: Optional[str],
    promo_footer: str,
    title_label: str = "Sarlavha",
    extra_footer: str = "",
    max_len: int = 1024
) -> str:
    """
    Telegram media caption (1024 belgi) limitiga moslab xavfsiz tuzish.
    HTML teglari hech qachon o'rtasidan kesilmaydi.
    """
    if not text_content:
        res = f"{header_info}{extra_footer}{promo_footer}"
        return res[:max_len]

    prefix = f"{header_info}💬 <b>{title_label}:</b>\n<blockquote>"
    suffix = f"</blockquote>\n{extra_footer}{promo_footer}"
    base_len = len(prefix) + len(suffix)

    if base_len >= max_len - 20:
        res = f"{header_info}{extra_footer}{promo_footer}"
        return res[:max_len]

    available = max(10, max_len - base_len - 3)
    if len(text_content) > available:
        text_content = text_content[:available] + "..."

    return f"{prefix}{html.escape(text_content)}{suffix}"


def format_sender_name(user: Optional[types.User]) -> str:
    """Foydalanuvchi ism-familiyasi va username ini qisqa formatlash."""
    if not user:
        return "Noma'lum"
    name = user.full_name or "Noma'lum"
    if user.username:
        return f"{name} (@{user.username})"
    return name


def format_chat_title(chat: types.Chat) -> str:
    """Chat nomini aniqlash."""
    if chat.title:
        return chat.title
    if chat.full_name:
        if chat.username:
            return f"{chat.full_name} (@{chat.username})"
        return chat.full_name
    return f"ID: {chat.id}"


def extract_media_info(message: types.Message) -> Tuple[str, Optional[str], str, Optional[str], Optional[Any]]:
    """Xabar turi, file_id, sarlavha va obyektni aniqlash."""
    if message.photo:
        photo = message.photo[-1]
        return "photo", photo.file_id, message.caption or "", "jpg", photo
    elif message.video:
        return "video", message.video.file_id, message.caption or "", "mp4", message.video
    elif message.voice:
        return "voice", message.voice.file_id, message.caption or "", "ogg", message.voice
    elif message.video_note:
        return "video_note", message.video_note.file_id, "", "mp4", message.video_note
    elif message.document:
        ext = "bin"
        if message.document.file_name and "." in message.document.file_name:
            ext = message.document.file_name.rsplit(".", 1)[-1].lower()
        return "document", message.document.file_id, message.caption or "", ext, message.document
    elif message.audio:
        ext = "mp3"
        if message.audio.file_name and "." in message.audio.file_name:
            ext = message.audio.file_name.rsplit(".", 1)[-1].lower()
        return "audio", message.audio.file_id, message.caption or "", ext, message.audio
    elif message.animation:
        return "animation", message.animation.file_id, message.caption or "", "mp4", message.animation
    elif message.sticker:
        ext = "webm" if message.sticker.is_video else ("tgs" if message.sticker.is_animated else "webp")
        return "sticker", message.sticker.file_id, "", ext, message.sticker
    else:
        return "text", None, message.text or "", None, None


async def _background_download_media(bot: Bot, downloadable: Any, ext: str, chat_id: int, message_id: int):
    """Media faylni asinxron orqa fonda yuklab olish (poller ni qotirmaslik uchun)."""
    try:
        file_size = getattr(downloadable, "file_size", 0) or 0
        if file_size > 20 * 1024 * 1024:
            return

        file_name = f"{abs(chat_id)}_{message_id}.{ext}"
        destination = MEDIA_DIR / file_name
        await bot.download(file=downloadable, destination=destination)
        await update_message_file_path(chat_id, message_id, str(destination))
    except Exception as e:
        logger.error(f"Fayl yuklashda xatolik ({chat_id}_{message_id}): {e}")


async def send_saved_media(
    bot: Bot,
    chat_id: int,
    content_type: str,
    file_path: Optional[str],
    file_id: Optional[str],
    caption: str
):
    """Media faylni egasiga tezkor yuborish."""
    file_to_send: Any = None
    if file_path and os.path.exists(file_path):
        file_to_send = FSInputFile(file_path)
    elif file_id:
        file_to_send = file_id

    if not file_to_send:
        await bot.send_message(chat_id, caption, parse_mode="HTML")
        return

    if len(caption) > 1000:
        await bot.send_message(chat_id, caption, parse_mode="HTML")
        caption = ""

    try:
        if content_type == "photo":
            await bot.send_photo(chat_id, photo=file_to_send, caption=caption, parse_mode="HTML")
        elif content_type == "voice":
            await bot.send_voice(chat_id, voice=file_to_send, caption=caption, parse_mode="HTML")
        elif content_type == "video":
            await bot.send_video(chat_id, video=file_to_send, caption=caption, parse_mode="HTML")
        elif content_type == "video_note":
            if caption:
                await bot.send_message(chat_id, caption, parse_mode="HTML")
            await bot.send_video_note(chat_id, video_note=file_to_send)
        elif content_type == "document":
            await bot.send_document(chat_id, document=file_to_send, caption=caption, parse_mode="HTML")
        elif content_type == "audio":
            await bot.send_audio(chat_id, audio=file_to_send, caption=caption, parse_mode="HTML")
        elif content_type == "animation":
            await bot.send_animation(chat_id, animation=file_to_send, caption=caption, parse_mode="HTML")
        elif content_type == "sticker":
            if caption:
                await bot.send_message(chat_id, caption, parse_mode="HTML")
            await bot.send_sticker(chat_id, sticker=file_to_send)
        else:
            await bot.send_message(chat_id, caption, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Media yuborishda xatolik ({content_type}): {e}")
        if file_id and file_to_send != file_id:
            try:
                if content_type == "photo":
                    await bot.send_photo(chat_id, photo=file_id, caption=caption, parse_mode="HTML")
                elif content_type == "voice":
                    await bot.send_voice(chat_id, voice=file_id, caption=caption, parse_mode="HTML")
                elif content_type == "video":
                    await bot.send_video(chat_id, video=file_id, caption=caption, parse_mode="HTML")
            except Exception:
                pass


@router.business_connection()
async def on_business_connection(connection: types.BusinessConnection, bot: Bot):
    """Profilga ulanish / uzilish hodisasi."""
    user_id = connection.user.id
    user_chat_id = connection.user_chat_id or user_id

    await save_connection(
        connection_id=connection.id,
        user_id=user_id,
        user_chat_id=user_chat_id,
        is_enabled=connection.is_enabled,
    )

    is_new_trial = False
    if connection.is_enabled:
        # Faqat akkauntini birinchi marta ulaganda 30 kunlik Free Trial beriladi
        is_new_trial = await ensure_free_trial(user_id)

    target_chat = user_chat_id or ADMIN_ID
    if target_chat:
        lang = await get_user_language(target_chat)
        user_name = html.escape(format_sender_name(connection.user))
        if connection.is_enabled:
            # Faqat birinchi marta trial berilganida 30 kunlik sinov matnini ko'rsatamiz
            trial_text = get_text("conn_trial", lang) if is_new_trial else ""
            text = get_text("conn_success", lang, user_name=user_name, user_id=user_id, trial_text=trial_text)

            # Agar bu user biror kishining referali bo'lsa, taklif qilganga +1 kun berish
            ref_reward = await process_referral_connection_reward(user_id)
            if ref_reward:
                referrer_id, new_exp = ref_reward
                ref_lang = await get_user_language(referrer_id)
                reward_msg = get_text("referral_reward_notify", ref_lang, expires_at=new_exp)
                try:
                    await bot.send_message(referrer_id, reward_msg, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"Referrer {referrer_id} ga xabar yuborishda xatolik: {e}")
        else:
            text = get_text("conn_disabled", lang, user_name=user_name, user_id=user_id)
        try:
            await bot.send_message(target_chat, text, parse_mode="HTML")
        except Exception:
            pass


@router.business_message()
async def on_business_message(message: types.Message, bot: Bot):
    """Tezkor xabar qabul qilish (Non-blocking / Yuqori tezlik)."""
    conn_id = message.business_connection_id or ""
    chat_title = format_chat_title(message.chat)
    content_type, file_id, text_content, ext, downloadable = extract_media_info(message)

    sender_id = message.from_user.id if message.from_user else 0
    sender_name = format_sender_name(message.from_user)
    sender_username = message.from_user.username or "" if message.from_user else ""

    is_from_me = False
    if message.chat.type == "private" and message.from_user:
        is_from_me = (message.from_user.id != message.chat.id)

    date_str = (
        message.date.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if message.date
        else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    )

    # 1. Bazaga bir zumda yozish (<0.5ms)
    await save_message(
        connection_id=conn_id,
        chat_id=message.chat.id,
        chat_title=chat_title,
        message_id=message.message_id,
        sender_id=sender_id,
        sender_name=sender_name,
        sender_username=sender_username,
        is_from_me=is_from_me,
        content_type=content_type,
        text=text_content,
        file_id=file_id,
        file_path=None,
        created_at=date_str,
    )

    # 2. Agar media bo'lsa, yuklab olishni fon vazifasiga berish (handler bloklanmaydi)
    if downloadable and file_id and ext:
        asyncio.create_task(
            _background_download_media(
                bot=bot,
                downloadable=downloadable,
                ext=ext,
                chat_id=message.chat.id,
                message_id=message.message_id
            )
        )

    # 3. Faqat foydalanuvchi (biznes hisob egasi) suhbatdoshning 1 martalik mediasiga
    # javob (Reply) berganida ishlaydi! Suhbatdoshdan kelgan oddiy xabarlarga tegilmaydi.
    if is_from_me and message.reply_to_message:
        asyncio.create_task(
            handle_reply_media_capture(
                bot=bot,
                message=message,
                conn_id=conn_id,
                chat_title=chat_title,
                is_from_me=is_from_me,
            )
        )


@router.edited_business_message()
async def on_edited_business_message(message: types.Message, bot: Bot):
    """Xabar tahrirlanganda eski va yangi matnni foydalanuvchiga yuborish."""
    conn_id = message.business_connection_id
    content_type, file_id, new_text, ext, downloadable = extract_media_info(message)
    
    old_msg = await get_message(message.chat.id, message.message_id)
    await update_message_text(message.chat.id, message.message_id, new_text)

    old_text = (old_msg.get("text") or "").strip() if old_msg else ""
    clean_new_text = (new_text or "").strip()

    if old_msg and old_text and clean_new_text and old_text != clean_new_text:
        owner_chat_id = await resolve_owner_chat_id(bot, conn_id)
        if not owner_chat_id:
            return

        sub_status = await get_user_subscription_status(owner_chat_id, ADMIN_ID)
        is_active = sub_status["is_active"]
        lang = await get_user_language(owner_chat_id)
        who = ("Вы" if lang == "ru" else "Siz") if old_msg.get("is_from_me") else ("Собеседник" if lang == "ru" else "Suhbatdosh")
        sender_name = old_msg.get("sender_name") or format_sender_name(message.from_user)
        chat_title = format_chat_title(message.chat)
        sent_time = format_time_utc5(message.date)

        # 1. Shaxsiy arxiv kanaliga jo'natish
        archive_content = f"Oldingi holati:\n{old_text}\n\nYangi holati:\n{clean_new_text}"
        channel_msg_id = await archive_to_channel(
            bot=bot,
            owner_chat_id=owner_chat_id,
            chat_title=chat_title,
            who=who,
            sender_name=sender_name,
            sent_time=sent_time,
            content_type="text",
            text_content=archive_content,
            file_path=None,
            file_id=None,
            event_tag="#EDITED",
            event_title="✏️ <b>Tahrirlangan xabar</b>"
        )

        if channel_msg_id:
            await save_archive_log(
                user_id=owner_chat_id,
                chat_id=message.chat.id,
                channel_msg_id=channel_msg_id,
                event_type="edited",
                is_delivered=is_active
            )

        # 2. Obunasi bo'lsa xabarni yuborish
        if is_active:
            # 4000 belgiga moslab xavfsiz qisqartirish
            max_item = 1800
            t_old = old_text[:max_item] + "..." if len(old_text) > max_item else old_text
            t_new = clean_new_text[:max_item] + "..." if len(clean_new_text) > max_item else clean_new_text

            edit_text = (
                get_text(
                    "msg_edited",
                    lang,
                    who=who,
                    sender_name=html.escape(sender_name),
                    chat_title=html.escape(chat_title),
                    old_text=html.escape(t_old),
                    new_text=html.escape(t_new)
                )
                + get_text("promo_footer", lang)
            )
            try:
                await bot.send_message(owner_chat_id, edit_text, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Tahrirlangan xabarni yuborishda xatolik: {e}")
        else:
            # Obunasi bo'lmagan foydalanuvchiga Teaser
            total_missed = await count_undelivered_messages(owner_chat_id)
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=get_text("btn_unlock", lang, total_missed=total_missed), callback_data="show_plans")]
                ]
            )
            teaser_msg = (
                get_text("teaser_edited_title", lang) +
                get_text("teaser_edited_body", lang, total_missed=total_missed)
            )
            try:
                await bot.send_message(owner_chat_id, teaser_msg, reply_markup=kb, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Edited teaser yuborishda xatolik: {e}")




async def archive_to_channel(
    bot: Bot,
    owner_chat_id: int,
    chat_title: str,
    who: str,
    sender_name: str,
    sent_time: str,
    content_type: str,
    text_content: str,
    file_path: Optional[str],
    file_id: Optional[str],
    event_tag: str = "#DELETED",
    event_title: str = "🗑 <b>O'chirilgan xabar</b>"
) -> Optional[int]:
    """O'chirilgan yoki 1 martalik xabarni zaxira kanaliga yuborish va kanaldagi message_id ni qaytarish."""
    if not ARCHIVE_CHANNEL_ID:
        return None

    header = (
        f"#ARCHIVE #UID_{owner_chat_id} {event_tag}\n"
        f"{event_title}\n"
        f"👤 <b>Kimdan:</b> {who} ({html.escape(sender_name)})\n"
        f"👥 <b>Chat:</b> {html.escape(chat_title)}\n"
        f"🕒 <b>Vaqt:</b> {sent_time}\n"
    )

    try:
        if content_type == "text":
            body = safe_build_text_message(
                header_info=header,
                text_content=text_content,
                promo_footer="",
                msg_label="Xabar",
                max_len=4000
            )
            sent_msg = await bot.send_message(ARCHIVE_CHANNEL_ID, body, parse_mode="HTML")
            return sent_msg.message_id
        else:
            caption = safe_build_caption(
                header_info=header,
                text_content=text_content,
                promo_footer="",
                title_label="Sarlavha",
                extra_footer="",
                max_len=1024
            )

            file_to_send: Any = None
            if file_path and os.path.exists(file_path):
                file_to_send = FSInputFile(file_path)
            elif file_id:
                file_to_send = file_id

            if not file_to_send:
                sent_msg = await bot.send_message(ARCHIVE_CHANNEL_ID, caption, parse_mode="HTML")
                return sent_msg.message_id

            if content_type == "photo":
                sent_msg = await bot.send_photo(ARCHIVE_CHANNEL_ID, photo=file_to_send, caption=caption, parse_mode="HTML")
            elif content_type == "voice":
                sent_msg = await bot.send_voice(ARCHIVE_CHANNEL_ID, voice=file_to_send, caption=caption, parse_mode="HTML")
            elif content_type == "video":
                sent_msg = await bot.send_video(ARCHIVE_CHANNEL_ID, video=file_to_send, caption=caption, parse_mode="HTML")
            elif content_type == "video_note":
                await bot.send_message(ARCHIVE_CHANNEL_ID, caption, parse_mode="HTML")
                sent_msg = await bot.send_video_note(ARCHIVE_CHANNEL_ID, video_note=file_to_send)
            elif content_type == "document":
                sent_msg = await bot.send_document(ARCHIVE_CHANNEL_ID, document=file_to_send, caption=caption, parse_mode="HTML")
            elif content_type == "audio":
                sent_msg = await bot.send_audio(ARCHIVE_CHANNEL_ID, audio=file_to_send, caption=caption, parse_mode="HTML")
            elif content_type == "animation":
                sent_msg = await bot.send_animation(ARCHIVE_CHANNEL_ID, animation=file_to_send, caption=caption, parse_mode="HTML")
            elif content_type == "sticker":
                await bot.send_message(ARCHIVE_CHANNEL_ID, caption, parse_mode="HTML")
                sent_msg = await bot.send_sticker(ARCHIVE_CHANNEL_ID, sticker=file_to_send)
            else:
                sent_msg = await bot.send_message(ARCHIVE_CHANNEL_ID, caption, parse_mode="HTML")
            return sent_msg.message_id
    except Exception as e:
        logger.error(f"Arxiv kanaliga jo'natishda xatolik: {e}")
        return None


async def handle_reply_media_capture(
    bot: Bot,
    message: types.Message,
    conn_id: str,
    chat_title: str,
    is_from_me: bool,
):
    """Foydalanuvchi 1 martalik (taymerli) mediaga javob (Reply) berganida uni saqlash va yuborish."""
    # Faqat biznes hisob egasi reply qilgandagina ishlaydi
    if not is_from_me:
        return

    replied = message.reply_to_message
    if not replied:
        return

    r_type, r_file_id, r_caption, r_ext, r_down = extract_media_info(replied)
    if r_type == "text" or not r_file_id or not r_down or not r_ext:
        return

    r_sender_id = replied.from_user.id if replied.from_user else 0
    r_sender_name = format_sender_name(replied.from_user)
    r_sender_username = replied.from_user.username or "" if replied.from_user else ""
    r_date_str = (
        replied.date.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if replied.date
        else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    )

    # Ulanish egasini aniqlash
    owner_chat = await resolve_owner_chat_id(bot, conn_id)
    if not owner_chat:
        return

    # Faqat suhbatdoshdan kelgan mediaga javob berilganda ishlaydi (foydalanuvchi o'ziga o'zi yuborgan bo'lmasa)
    if r_sender_id == owner_chat:
        return

    # 1. BAZADA MAVJUDLIKNI TEKSHIRISH (1-USUL: FAQAT 1 MARTALIK MEDIA FILTRI):
    # Oddiy media kelgan paytda Telegram Bot API uni botimizga uzatgan va u allaqachon messages jadvalida mavjud bo'ladi.
    # 1 martalik (taymerli) media kelganida esa Telegram Bot API uni butunlay yashiradi (bazada bo'lmaydi).
    # Shuning uchun agar xabar bazada ALLAQACHON MAVJUD bo'lsa -> Bu 100% ODDIY media! Uni saqlamaymiz.
    existing_msg = await get_message(message.chat.id, replied.message_id)
    if existing_msg is not None:
        logger.info(f"Replied media (chat={message.chat.id}, msg={replied.message_id}) bazada mavjud (oddiy media). 1 martalik media emas, o'tkazib yuborildi.")
        return

    # 2. Avval bu media ushlanganmi? (Takroriy reply larni oldini olish)
    if await is_media_already_captured(message.chat.id, replied.message_id):
        return

    # 3. Vaqt tekshiruvi: 1 martalik media yangi kelgan bo'lishi shart (24 soat ichida)
    if replied.date:
        msg_date = replied.date if replied.date.tzinfo else replied.date.replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        if (now_utc - msg_date).total_seconds() > 24 * 3600:
            logger.info(f"Replied media {replied.message_id} 24 soatdan eski. 1 martalik media emas deb hisoblandi.")
            return

    # Haqiqiy 1 martalik media aniqlandi!
    await mark_media_as_captured(message.chat.id, replied.message_id)

    # 1 martalik xabarni bazaga saqlab qo'yamiz:
    await save_message(
        connection_id=conn_id,
        chat_id=message.chat.id,
        chat_title=chat_title,
        message_id=replied.message_id,
        sender_id=r_sender_id,
        sender_name=r_sender_name,
        sender_username=r_sender_username,
        is_from_me=False,
        content_type=r_type,
        text=r_caption,
        file_id=r_file_id,
        file_path=None,
        created_at=r_date_str,
    )

    # Mediani darhol diskka yuklab olish
    file_name = f"ttl_{abs(message.chat.id)}_{replied.message_id}.{r_ext}"
    destination = MEDIA_DIR / file_name
    try:
        await bot.download(file=r_down, destination=destination)
        await update_message_file_path(message.chat.id, replied.message_id, str(destination))
    except Exception as e:
        logger.error(f"1 martalik mediani yuklab olishda xatolik: {e}")

    sub_status = await get_user_subscription_status(owner_chat, ADMIN_ID)
    is_active = sub_status["is_active"]
    days_since_expiry = sub_status["days_since_expiry"]

    if days_since_expiry > 30:
        logger.warning(f"User {owner_chat} obunasiz 30 kundan oshgan. Reply media arxivlanmadi.")
        return

    time_str = format_time_utc5(replied.date, time_only=True)
    full_time_str = format_time_utc5(replied.date, time_only=False)

    # 1. Shaxsiy arxiv kanaliga jo'natish
    channel_msg_id = await archive_to_channel(
        bot=bot,
        owner_chat_id=owner_chat,
        chat_title=chat_title,
        who="Suhbatdosh",
        sender_name=r_sender_name,
        sent_time=full_time_str,
        content_type=r_type,
        text_content=r_caption or "",
        file_path=str(destination) if destination.exists() else None,
        file_id=r_file_id,
        event_tag="#VIEW_ONCE",
        event_title="👁 <b>1 martalik (taymerli) media</b>"
    )

    # 2. Arxiv logiga yozish
    if channel_msg_id:
        await save_archive_log(
            user_id=owner_chat,
            chat_id=message.chat.id,
            channel_msg_id=channel_msg_id,
            event_type="view_once",
            is_delivered=is_active
        )

    lang = await get_user_language(owner_chat)

    # 3. Foydalanuvchiga yetkazish yoki Teaser yuborish
    if is_active:
        caption_label = "Подпись" if lang == "ru" else "Izoh"
        header_text = get_text(
            "msg_view_once",
            lang,
            sender_name=html.escape(r_sender_name),
            chat_title=html.escape(chat_title),
            time_str=time_str
        )
        user_caption = safe_build_caption(
            header_info=header_text,
            text_content=r_caption,
            promo_footer=get_text("promo_footer", lang),
            title_label=caption_label,
            extra_footer=get_text("msg_view_once_footer", lang),
            max_len=1024
        )

        await send_saved_media(
            bot=bot,
            chat_id=owner_chat,
            content_type=r_type,
            file_path=str(destination) if destination.exists() else None,
            file_id=r_file_id,
            caption=user_caption,
        )
        logger.info(f"✅ 1 martalik media bot chatiga muvaffaqiyatli yetkazildi: {owner_chat}")

    else:
        # Obuna yo'q - teaser yuborish
        total_missed = await count_undelivered_messages(owner_chat)
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=get_text("btn_unlock", lang, total_missed=total_missed), callback_data="show_plans")]
            ]
        )
        teaser_msg = get_text("teaser_view_once", lang, total_missed=total_missed)
        try:
            await bot.send_message(owner_chat, teaser_msg, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Teaser yuborishda xatolik: {e}")


@router.deleted_business_messages()
async def on_deleted_business_messages(action: types.BusinessMessagesDeleted, bot: Bot):
    """Faqat o'chirilgan xabarlarni egasiga aniq va qisqa ko'rinishda yuborish."""
    conn_id = action.business_connection_id
    chat_id = action.chat.id

    owner_chat_id = await resolve_owner_chat_id(bot, conn_id)
    if not owner_chat_id:
        return

    lang = await get_user_language(owner_chat_id)

    # Obuna tekshiruvi (Admin uchun doimiy ochiq)
    sub_status = await get_user_subscription_status(owner_chat_id, ADMIN_ID)
    is_active = sub_status["is_active"]
    days_since_expiry = sub_status["days_since_expiry"]

    # 1 oylik (30 kun) limit: agar obunasiz 30 kundan oshsa, kanalga jo'natish foydasiz
    if days_since_expiry > 30:
        logger.warning(f"User {owner_chat_id} obunasiz 30 kundan oshgan ({days_since_expiry} kun). Arxivlash to'xtatilgan.")
        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=get_text("btn_renew_sub", lang), callback_data="show_plans")]
                ]
            )
            msg = get_text("scheduler_cutoff", lang)
            await bot.send_message(owner_chat_id, msg, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        return

    chat_title = format_chat_title(action.chat)
    saved_any_count = 0

    for msg_id in action.message_ids:
        msg = await get_message(chat_id, msg_id)

        if msg:
            # Agar bu media 1 martalik media sifatida reply orqali allaqachon yetkazilgan bo'lsa,
            # taymer tugab o'chirilganda foydalanuvchiga qayta "O'chirilgan xabar" deb dublikat yubormaymiz
            if await is_media_already_captured(chat_id, msg_id):
                logger.info(f"O'chirilgan media {msg_id} allaqachon 1 martalik media sifatida yetkazilgan. Dublikat xabar yuborilmadi.")
                continue

            who = ("Вы" if lang == "ru" else "Siz") if msg.get("is_from_me") else ("Собеседник" if lang == "ru" else "Suhbatdosh")
            sender_name = msg.get("sender_name") or ("Неизвестно" if lang == "ru" else "Noma'lum")
            sent_time = format_time_utc5(msg.get("created_at"))
            content_type = msg.get("content_type") or "text"
            text_content = msg.get("text") or ""
            file_id = msg.get("file_id")
            file_path = msg.get("file_path")

            # 1. Shaxsiy arxiv kanaliga jo'natish (agar kanal sozlangan bo'lsa)
            channel_msg_id = await archive_to_channel(
                bot=bot,
                owner_chat_id=owner_chat_id,
                chat_title=chat_title,
                who=who,
                sender_name=sender_name,
                sent_time=sent_time,
                content_type=content_type,
                text_content=text_content,
                file_path=file_path,
                file_id=file_id
            )

            # 2. Arxiv logiga yozish
            if channel_msg_id:
                await save_archive_log(
                    user_id=owner_chat_id,
                    chat_id=chat_id,
                    channel_msg_id=channel_msg_id,
                    event_type="deleted",
                    is_delivered=is_active
                )
            saved_any_count += 1

            # 3. Agar foydalanuvchida faol obuna bo'lsa, xabarni to'liq ko'rsatish
            if is_active:
                header_info = (
                    get_text("msg_deleted_title", lang) +
                    f"👤 <b>{'От' if lang == 'ru' else 'Kimdan'}:</b> {who} ({html.escape(sender_name)})\n"
                    f"👥 <b>{'Чат' if lang == 'ru' else 'Chat'}:</b> {html.escape(chat_title)}\n"
                    f"🕒 <b>{'Время' if lang == 'ru' else 'Vaqt'}:</b> {sent_time}\n"
                )

                try:
                    promo_footer = get_text("promo_footer", lang)
                    if content_type == "text":
                        msg_label = "Сообщение" if lang == "ru" else "Xabar"
                        body = safe_build_text_message(
                            header_info=header_info,
                            text_content=text_content,
                            promo_footer=promo_footer,
                            msg_label=msg_label,
                            max_len=4000
                        )
                        await bot.send_message(owner_chat_id, body, parse_mode="HTML")
                    else:
                        title_label = "Подпись" if lang == "ru" else "Sarlavha"
                        caption = safe_build_caption(
                            header_info=header_info,
                            text_content=text_content,
                            promo_footer=promo_footer,
                            title_label=title_label,
                            extra_footer="",
                            max_len=1024
                        )

                        await send_saved_media(
                            bot=bot,
                            chat_id=owner_chat_id,
                            content_type=content_type,
                            file_path=file_path,
                            file_id=file_id,
                            caption=caption
                        )
                except Exception as e:
                    logger.error(f"O'chirilgan xabarni yuborishda xatolik: {e}")

            # Telegram FloodWait himoyasi: ko'p xabarlar o'chirilganda kichik kechikish
            await asyncio.sleep(0.3)


    # 4. Agar foydalanuvchida obuna BO'LMASA, xabar matni berilmaydi, teaser yuboriladi
    if not is_active and saved_any_count > 0:
        total_missed = await count_undelivered_messages(owner_chat_id)
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=get_text("btn_unlock", lang, total_missed=total_missed), callback_data="show_plans")]
            ]
        )
        msg = (
            get_text("teaser_deleted_title", lang) +
            get_text("teaser_deleted_body", lang, total_missed=total_missed)
        )
        try:
            await bot.send_message(owner_chat_id, msg, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Teaser yuborishda xatolik: {e}")

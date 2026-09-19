import urllib.parse
import html
import logging
from datetime import datetime
from aiogram import Router, types, Bot, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import (
    get_stats,
    is_subscription_active,
    get_subscription_info,
    get_user_language,
    set_user_language,
    register_referral,
    get_user_referral_stats,
    is_referral_enabled,
    is_user_business_connected,
    get_user_deleted_messages_count,
    get_user_subscription_status,
    is_user_language_set,
)
from config import ADMIN_ID, PRIVACY_POLICY_URL, GUIDE_CHANNEL_ID, GUIDE_MESSAGE_IDS
from locales import (
    get_text,
    get_main_keyboard,
    get_connected_keyboard,
    get_language_keyboard,
)

logger = logging.getLogger(__name__)
router = Router(name="common_router")


async def get_start_payload(user_id: int, user_name: str, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    """Foydalanuvchi ulangan yoki ulanmaganiga qarab mos start matni va klaviaturasini tayyorlash."""
    is_connected = await is_user_business_connected(user_id)

    if is_connected:
        sub_info = await get_user_subscription_status(user_id, ADMIN_ID)
        is_active = sub_info.get("is_active", False)
        plan_type = sub_info.get("plan_type", "none")
        expires_at_str = sub_info.get("expires_at")

        if user_id == ADMIN_ID:
            sub_status_text = "👑 " + ("Безлимитный (Админ)" if lang == "ru" else "Cheksiz (Admin)")
        elif is_active and expires_at_str:
            days_left = 0
            exp_dt = None
            if isinstance(expires_at_str, str):
                try:
                    clean = expires_at_str.replace("T", " ")[:19]
                    exp_dt = datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass
            elif isinstance(expires_at_str, datetime):
                exp_dt = expires_at_str.replace(tzinfo=None)

            if exp_dt:
                diff_sec = (exp_dt - datetime.now()).total_seconds()
                if diff_sec > 0:
                    import math
                    days_left = max(1, math.ceil(diff_sec / 86400))

            if plan_type == "free_trial":
                sub_status_text = (
                    f'<tg-emoji emoji-id="5193085063998224234">🎁</tg-emoji> Free Trial ({days_left} дн. осталось)'
                    if lang == "ru"
                    else f'<tg-emoji emoji-id="5193085063998224234">🎁</tg-emoji> Free Trial ({days_left} kun qoldi)'
                )
            else:
                sub_status_text = (
                    f"🟢 Активна ({days_left} дн. осталось)"
                    if lang == "ru"
                    else f"🟢 Faol ({days_left} kun qoldi)"
                )
        else:
            sub_status_text = "🔴 " + ("Подписка истекла" if lang == "ru" else "Obuna tugagan")

        deleted_count = await get_user_deleted_messages_count(user_id)

        text = get_text(
            "start_connected_text",
            lang,
            user_name=user_name,
            user_id=user_id,
            sub_status=sub_status_text,
            deleted_count=deleted_count
        )
        kb = get_connected_keyboard(lang=lang, is_admin=(user_id == ADMIN_ID))
        return text, kb

    # Ulanmagan foydalanuvchilar uchun
    text = get_text("start_text", lang)
    kb = get_main_keyboard(lang)
    return text, kb


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_name = html.escape(message.from_user.full_name or message.from_user.first_name or "Foydalanuvchi")

    # Referal parametrini tekshirish (masalan: /start ref_123456)
    if message.text:
        parts = message.text.split()
        if len(parts) > 1 and parts[1].startswith("ref_"):
            ref_str = parts[1].replace("ref_", "")
            if ref_str.isdigit():
                referrer_id = int(ref_str)
                await register_referral(referrer_id=referrer_id, referred_user_id=user_id)

    # Agar yangi foydalanuvchi bo'lsa va hali til tanlamagan bo'lsa, dastlab til tanlatamiz
    if not await is_user_language_set(user_id):
        welcome_lang_text = (
            '<tg-emoji emoji-id="5447410659077661506">🌐</tg-emoji> <b>Iltimos, tilni tanlang / Пожалуйста, выберите язык:</b>'
        )
        await message.answer(
            welcome_lang_text,
            reply_markup=get_language_keyboard(lang="ru", is_first_time=True),
            parse_mode="HTML"
        )
        return

    lang = await get_user_language(user_id)
    text, kb = await get_start_payload(user_id=user_id, user_name=user_name, lang=lang)

    await message.answer(
        text,
        reply_markup=kb,
        parse_mode="HTML"
    )



@router.message(Command("status"))
async def cmd_status(message: types.Message):
    lang = await get_user_language(message.from_user.id)
    stats = await get_stats()
    status_icon = "🟢" if stats['active_connections'] > 0 else "⚪️"
    is_active = await is_subscription_active(message.from_user.id, ADMIN_ID)
    sub_info = await get_subscription_info(message.from_user.id)

    if is_active:
        if message.from_user.id == ADMIN_ID:
            sub_status_text = get_text("sub_admin", lang)
        elif sub_info:
            sub_status_text = f"🟢 {sub_info.get('expires_at')}"
        else:
            sub_status_text = get_text("sub_inactive", lang)
    else:
        sub_status_text = get_text("sub_inactive", lang)

    body = (
        get_text("status_title", lang, status_icon=status_icon) +
        get_text("status_connections", lang, active_connections=stats['active_connections']) +
        get_text("status_messages", lang, total_messages=stats['total_messages']) +
        get_text("status_subscription", lang, sub_status=sub_status_text) +
        get_text("status_footer", lang)
    )

    await message.answer(
        body,
        reply_markup=get_main_keyboard(lang),
        parse_mode="HTML"
    )


@router.message(Command("lang"))
@router.message(Command("language"))
@router.callback_query(F.data == "choose_lang")
async def cmd_language(event: types.Message | types.CallbackQuery):
    """Til tanlash menyusini ko'rsatish."""
    user_id = event.from_user.id
    lang = await get_user_language(user_id)
    text = get_text("choose_lang", lang)

    if isinstance(event, types.CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=get_language_keyboard(lang), parse_mode="HTML")
        except Exception:
            pass
        await event.answer()
    else:
        await event.answer(text, reply_markup=get_language_keyboard(lang), parse_mode="HTML")


@router.callback_query(F.data.startswith("set_lang:"))
async def cb_set_language(call: types.CallbackQuery):
    """Foydalanuvchi tilini o'zgartirish."""
    user_id = call.from_user.id
    new_lang = call.data.split(":")[1]
    if new_lang not in ["ru", "uz"]:
        new_lang = "ru"

    await set_user_language(user_id, new_lang)
    confirm_text = get_text("lang_selected", new_lang)
    user_name = html.escape(call.from_user.full_name or call.from_user.first_name or "Foydalanuvchi")
    text, kb = await get_start_payload(user_id=user_id, user_name=user_name, lang=new_lang)

    try:
        await call.message.edit_text(
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception:
        try:
            await call.message.answer(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
    await call.answer(confirm_text)


@router.callback_query(F.data == "back_to_menu")
async def cb_back_to_menu(call: types.CallbackQuery):
    """Bosh menyuga qaytish."""
    user_id = call.from_user.id
    lang = await get_user_language(user_id)
    user_name = html.escape(call.from_user.full_name or call.from_user.first_name or "Foydalanuvchi")
    text, kb = await get_start_payload(user_id=user_id, user_name=user_name, lang=lang)

    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        try:
            await call.message.answer(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
    await call.answer()


@router.message(Command("guide"))
@router.message(Command("help"))
@router.callback_query(F.data == "show_guide")
async def cb_show_guide(event: types.Message | types.CallbackQuery, bot: Bot):
    """Qo'llanma videolari va tushuntirish matnini ko'rsatish."""
    user_id = event.from_user.id
    lang = await get_user_language(user_id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="back_to_menu")]
        ]
    )

    if isinstance(event, types.CallbackQuery):
        await event.answer()
        try:
            await event.message.delete()
        except Exception:
            pass

    # Videolarni kanaldan nusxalab yuborish
    try:
        await bot.copy_messages(
            chat_id=user_id,
            from_chat_id=GUIDE_CHANNEL_ID,
            message_ids=GUIDE_MESSAGE_IDS
        )
    except Exception as e:
        logger.error(f"Qo'llanma videolarini nusxalashda xatolik: {e}")

    # Qo'llanma tavsif matni va [Orqaga] tugmasi
    await bot.send_message(
        chat_id=user_id,
        text=get_text("guide_text", lang),
        reply_markup=kb,
        parse_mode="HTML"
    )



@router.callback_query(F.data == "refresh_stats")
async def cb_stats(call: types.CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    stats = await get_stats()
    status_icon = "🟢" if stats['active_connections'] > 0 else "⚪️"
    is_active = await is_subscription_active(call.from_user.id, ADMIN_ID)
    sub_info = await get_subscription_info(call.from_user.id)

    if is_active:
        if call.from_user.id == ADMIN_ID:
            sub_status_text = get_text("sub_admin", lang)
        elif sub_info:
            sub_status_text = f"🟢 {sub_info.get('expires_at')}"
        else:
            sub_status_text = get_text("sub_inactive", lang)
    else:
        sub_status_text = get_text("sub_inactive", lang)

    body = (
        get_text("status_title", lang, status_icon=status_icon) +
        get_text("status_connections", lang, active_connections=stats['active_connections']) +
        get_text("status_messages", lang, total_messages=stats['total_messages']) +
        get_text("status_subscription", lang, sub_status=sub_status_text) +
        get_text("status_footer", lang)
    )

    try:
        await call.message.edit_text(body, reply_markup=get_main_keyboard(lang), parse_mode="HTML")
    except Exception:
        pass
    await call.answer()


@router.message(Command("ref"))
@router.message(Command("referral"))
@router.callback_query(F.data == "show_referral")
async def cb_show_referral(event: types.Message | types.CallbackQuery, bot: Bot):
    """Referal tizimi menyusi."""
    user_id = event.from_user.id
    lang = await get_user_language(user_id)

    if not await is_referral_enabled():
        text = get_text("referral_disabled", lang)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="back_to_menu")]]
        )
        if isinstance(event, types.CallbackQuery):
            await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            await event.answer()
        else:
            await event.answer(text, reply_markup=kb, parse_mode="HTML")
        return

    # Bot username olish
    bot_info = await bot.get_me()
    bot_username = bot_info.username or "seenspybot"
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    stats = await get_user_referral_stats(user_id)
    title = get_text("referral_title", lang)
    body = get_text(
        "referral_body",
        lang,
        invited=stats["total_invited"],
        max_limit=stats["max_limit"],
        connected=stats["total_connected"],
        reward_days=stats["reward_days"],
        remaining=stats["remaining_slots"],
        ref_link=ref_link,
    )

    share_text = get_text("share_text", lang)
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={urllib.parse.quote(share_text)}"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text("btn_share_ref", lang), url=share_url)],
            [InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="back_to_menu")],
        ]
    )

    if isinstance(event, types.CallbackQuery):
        try:
            await event.message.edit_text(f"{title}{body}", reply_markup=kb, parse_mode="HTML")
        except Exception:
            await event.message.answer(f"{title}{body}", reply_markup=kb, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(f"{title}{body}", reply_markup=kb, parse_mode="HTML")


@router.message(Command("privacy"))
async def cmd_privacy(message: types.Message):
    """Maxfiylik siyosati (Privacy Policy) komandasi."""
    lang = await get_user_language(message.from_user.id)
    text = get_text("privacy_text", lang)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text("btn_privacy", lang), url=PRIVACY_POLICY_URL)],
            [InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="back_to_menu")]
        ]
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


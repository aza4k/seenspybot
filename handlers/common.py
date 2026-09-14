import urllib.parse
from aiogram import Router, types, Bot, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import (
    get_stats,
    is_subscription_active,
    get_subscription_info,
    ensure_free_trial,
    get_user_language,
    set_user_language,
    register_referral,
    get_user_referral_stats,
    is_referral_enabled,
)
from config import ADMIN_ID, PRIVACY_POLICY_URL
from locales import (
    get_text,
    get_main_keyboard,
    get_language_keyboard,
)


router = Router(name="common_router")


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    # Referal parametrini tekshirish (masalan: /start ref_123456)
    if message.text:
        parts = message.text.split()
        if len(parts) > 1 and parts[1].startswith("ref_"):
            ref_str = parts[1].replace("ref_", "")
            if ref_str.isdigit():
                referrer_id = int(ref_str)
                await register_referral(referrer_id=referrer_id, referred_user_id=message.from_user.id)

    # Yangi foydalanuvchiga 7 kunlik Free Trial berish
    is_new_trial = await ensure_free_trial(message.from_user.id)
    lang = await get_user_language(message.from_user.id)
    is_active = await is_subscription_active(message.from_user.id, ADMIN_ID)
    sub_info = await get_subscription_info(message.from_user.id)

    trial_banner = get_text("trial_banner", lang) if is_new_trial else ""

    if is_active:
        if message.from_user.id == ADMIN_ID:
            sub_status = get_text("sub_admin", lang)
        elif sub_info:
            plan_name = (
                get_text("sub_trial_name", lang)
                if sub_info.get("plan_type") == "free_trial"
                else sub_info.get("plan_type")
            )
            sub_status = get_text(
                "sub_active",
                lang,
                plan_name=plan_name,
                expires_at=sub_info.get("expires_at", "")
            )
        else:
            sub_status = get_text("sub_inactive", lang)
    else:
        sub_status = get_text("sub_inactive", lang)

    text = get_text(
        "start_text",
        lang,
        trial_banner=trial_banner,
        sub_status=sub_status
    )

    await message.answer(
        text,
        reply_markup=get_main_keyboard(lang),
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
            await event.message.edit_text(text, reply_markup=get_language_keyboard(), parse_mode="HTML")
        except Exception:
            pass
        await event.answer()
    else:
        await event.answer(text, reply_markup=get_language_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("set_lang:"))
async def cb_set_language(call: types.CallbackQuery):
    """Foydalanuvchi tilini o'zgartirish."""
    new_lang = call.data.split(":")[1]
    if new_lang not in ["ru", "uz"]:
        new_lang = "ru"

    await set_user_language(call.from_user.id, new_lang)
    confirm_text = get_text("lang_selected", new_lang)

    try:
        await call.message.edit_text(
            confirm_text,
            reply_markup=get_main_keyboard(new_lang),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data == "back_to_menu")
async def cb_back_to_menu(call: types.CallbackQuery):
    """Bosh menyuga qaytish."""
    lang = await get_user_language(call.from_user.id)
    is_active = await is_subscription_active(call.from_user.id, ADMIN_ID)
    sub_status = get_text("sub_active", lang, plan_name="", expires_at="") if is_active else get_text("sub_inactive", lang)

    trial_banner = ""
    text = get_text(
        "start_text",
        lang,
        trial_banner=trial_banner,
        sub_status=sub_status
    )

    try:
        await call.message.edit_text(text, reply_markup=get_main_keyboard(lang), parse_mode="HTML")
    except Exception:
        pass
    await call.answer()


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


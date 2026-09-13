import asyncio
import logging
from aiogram import Router, Bot, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
)
from database import (
    is_subscription_active,
    add_subscription,
    get_subscription_info,
    get_undelivered_archive_logs,
    mark_archive_logs_delivered,
    get_user_language,
)
from config import ADMIN_ID, ARCHIVE_CHANNEL_ID
from locales import get_text, get_plans_keyboard

logger = logging.getLogger(__name__)
router = Router(name="payments_router")

PLANS = {
    "week": {
        "days": 7,
        "stars": 5,
    },
    "month": {
        "days": 30,
        "stars": 15,
    },
    "year": {
        "days": 365,
        "stars": 180,
    },
}


@router.message(Command("buy"))
@router.message(Command("plans"))
async def cmd_buy(message: types.Message):
    """Tariflar menyusini ochish."""
    lang = await get_user_language(message.from_user.id)
    text = get_text("plans_title", lang)
    await message.answer(text, reply_markup=get_plans_keyboard(lang), parse_mode="HTML")


@router.callback_query(F.data == "show_plans")
async def cb_show_plans(call: types.CallbackQuery):
    """Inline tugma orqali tariflar menyusi."""
    lang = await get_user_language(call.from_user.id)
    text = get_text("plans_title", lang)
    try:
        await call.message.edit_text(text, reply_markup=get_plans_keyboard(lang), parse_mode="HTML")
    except Exception:
        await call.message.answer(text, reply_markup=get_plans_keyboard(lang), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy_plan(call: types.CallbackQuery, bot: Bot):
    """Telegram Stars Invoice (to'lov hisobini) chiqarish."""
    plan_key = call.data.split(":")[1]
    plan = PLANS.get(plan_key)

    if not plan:
        await call.answer("Tarif topilmadi!", show_alert=True)
        return

    lang = await get_user_language(call.from_user.id)
    plan_name = get_text(f"plan_{plan_key}_name", lang)
    plan_desc = get_text(f"plan_{plan_key}_desc", lang)

    prices = [LabeledPrice(label=plan_name, amount=plan["stars"])]

    try:
        await bot.send_invoice(
            chat_id=call.from_user.id,
            title=f"⭐ {plan_name}",
            description=plan_desc,
            payload=f"sub_{plan_key}",
            currency="XTR",
            prices=prices,
            provider_token="",  # Telegram Stars uchun bo'sh qoldiriladi
        )
        await call.answer()
    except Exception as e:
        logger.error(f"Invoice yuborishda xatolik: {e}")
        await call.answer(f"Xatolik yuz berdi: {e}", show_alert=True)


@router.pre_checkout_query()
async def on_pre_checkout_query(pre_checkout_q: PreCheckoutQuery):
    """Telegram to'lovni tasdiqlash so'rovi (Pre-checkout)."""
    await pre_checkout_q.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: types.Message, bot: Bot):
    """Muvaffaqiyatli to'lov amalga oshirilganda ishlaydi."""
    payment = message.successful_payment
    payload = payment.invoice_payload or ""
    stars_amount = payment.total_amount

    # Payload dan qaysi tarif olinganini aniqlash
    plan_key = "week"
    if "month" in payload:
        plan_key = "month"
    elif "year" in payload:
        plan_key = "year"

    plan = PLANS.get(plan_key, PLANS["week"])
    new_expiry = await add_subscription(
        user_id=message.from_user.id,
        days=plan["days"],
        plan_type=plan_key,
        stars_paid=stars_amount
    )

    lang = await get_user_language(message.from_user.id)
    plan_name = get_text(f"plan_{plan_key}_name", lang)

    logger.info(
        f"⭐ Yangi to'lov: User={message.from_user.id}, Tarif={plan_name}, Stars={stars_amount}, Muddat={new_expiry}"
    )

    congrat_text = get_text(
        "payment_success",
        lang,
        plan_name=plan_name,
        expires_at=new_expiry
    )
    await message.answer(congrat_text, parse_mode="HTML")

    # To'lovgacha yig'ilib qolgan ochilmagan arxiv xabarlarini tiklab berish
    user_id = message.from_user.id
    undelivered_logs = await get_undelivered_archive_logs(user_id)

    if undelivered_logs and ARCHIVE_CHANNEL_ID:
        total = len(undelivered_logs)
        await message.answer(
            get_text("payment_replay_header", lang, count=total),
            parse_mode="HTML"
        )

        delivered_count = 0
        for log in undelivered_logs:
            try:
                channel_msg_id = log["channel_msg_id"]
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=ARCHIVE_CHANNEL_ID,
                    message_id=channel_msg_id
                )
                delivered_count += 1
                await asyncio.sleep(0.35)  # Telegram FloodLimit himoyasi
            except Exception as e:
                logger.error(f"Xabarni tiklashda xatolik (channel_msg_id={log.get('channel_msg_id')}): {e}")

        await mark_archive_logs_delivered(user_id)
        if lang == "ru":
            done_text = f"✅ <b>Все {delivered_count} сохранённых сообщений успешно доставлены!</b>"
        else:
            done_text = f"✅ <b>Barcha to'plangan {delivered_count} ta xabarlar muvaffaqiyatli yetkazildi!</b>"
        await message.answer(done_text, parse_mode="HTML")

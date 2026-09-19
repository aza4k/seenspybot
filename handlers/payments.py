import asyncio
import logging
from datetime import datetime
from aiogram import Router, Bot, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
)
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from database import (
    is_subscription_active,
    add_subscription,
    get_subscription_info,
    get_undelivered_archive_logs,
    mark_archive_logs_delivered,
    get_user_language,
    get_user_subscription_status,
)
from config import ADMIN_ID, ARCHIVE_CHANNEL_ID
from locales import get_text, get_plans_keyboard, MESSAGES

logger = logging.getLogger(__name__)
router = Router(name="payments_router")

PLANS = {
    "week": {
        "days": 7,
        "stars": 25,
    },
    "month": {
        "days": 28,
        "stars": 59,
    },
    "year": {
        "days": 365,
        "stars": 290,
    },
}


def format_remaining_time(days: int, hours: int, lang: str) -> str:
    """Qolgan muddatni chiroyli formatda chiqarish."""
    if lang == "uz":
        if days > 0:
            return f"{days} kun {hours} soat"
        elif hours > 0:
            return f"{hours} soat"
        return "1 soatdan kam"
    else:
        if days > 0:
            if days % 10 == 1 and days % 100 != 11:
                d_word = "день"
            elif 2 <= days % 10 <= 4 and (days % 100 < 10 or days % 100 >= 20):
                d_word = "дня"
            else:
                d_word = "дней"
            return f"{days} {d_word} {hours} ч."
        elif hours > 0:
            return f"{hours} ч."
        return "менее 1 часа"


async def get_plans_text(user_id: int, lang: str) -> str:
    """Tariflar xabarini foydalanuvchi joriy obunasi bilan birga tuzish."""
    status = await get_user_subscription_status(user_id, ADMIN_ID)
    if user_id == ADMIN_ID:
        header = get_text("plans_current_admin", lang)
    elif status.get("is_active"):
        plan_type = status.get("plan_type", "active")
        if plan_type == "free_trial":
            plan_name = get_text("sub_trial_name", lang)
        elif f"plan_{plan_type}_name" in MESSAGES.get(lang, {}):
            plan_name = get_text(f"plan_{plan_type}_name", lang)
        else:
            plan_name = plan_type

        expires_at_str = status.get("expires_at", "")
        remaining_str = "—"
        if expires_at_str:
            try:
                exp_date = None
                if isinstance(expires_at_str, str):
                    clean = expires_at_str.replace("T", " ")[:19]
                    exp_date = datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
                elif isinstance(expires_at_str, datetime):
                    exp_date = expires_at_str.replace(tzinfo=None)
                if exp_date:
                    now = datetime.now()
                    diff = exp_date - now
                    if diff.total_seconds() > 0:
                        days = diff.days
                        hours = int(diff.seconds / 3600)
                        remaining_str = format_remaining_time(days, hours, lang)
            except Exception:
                remaining_str = "—"

        header = get_text(
            "plans_current_active",
            lang,
            plan_name=plan_name,
            remaining_str=remaining_str,
            expires_at=expires_at_str,
        )
    else:
        header = ""

    ref_link = f"https://t.me/seenspybot?start=ref_{user_id}"
    return header + get_text("plans_title", lang, ref_link=ref_link)


@router.message(Command("buy"))
@router.message(Command("plans"))
async def cmd_buy(message: types.Message):
    """Tariflar menyusini ochish."""
    lang = await get_user_language(message.from_user.id)
    text = await get_plans_text(message.from_user.id, lang)
    await message.answer(text, reply_markup=get_plans_keyboard(lang), parse_mode="HTML")


@router.callback_query(F.data == "show_plans")
async def cb_show_plans(call: types.CallbackQuery):
    """Inline tugma orqali tariflar menyusi."""
    lang = await get_user_language(call.from_user.id)
    text = await get_plans_text(call.from_user.id, lang)
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

    # To'lovgacha yig'ilib qolgan ochilmagan arxiv xabarlarini orqa fonda tiklab berish
    user_id = message.from_user.id
    undelivered_logs = await get_undelivered_archive_logs(user_id)

    if undelivered_logs and ARCHIVE_CHANNEL_ID:
        total = len(undelivered_logs)
        await message.answer(
            get_text("payment_replay_header", lang, count=total),
            parse_mode="HTML"
        )
        asyncio.create_task(
            _replay_missed_archive_messages(bot, user_id, undelivered_logs, lang)
        )


async def _replay_missed_archive_messages(bot: Bot, user_id: int, undelivered_logs: list, lang: str):
    """Obunasiz paytda o'tkazib yuborilgan xabarlarni orqa fonda asinxron yetkazish."""
    if not undelivered_logs or not ARCHIVE_CHANNEL_ID:
        return

    MAX_REPLAY = 30
    total = len(undelivered_logs)
    logs_to_replay = undelivered_logs[-MAX_REPLAY:]

    delivered_count = 0
    for log in logs_to_replay:
        try:
            channel_msg_id = log["channel_msg_id"]
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=ARCHIVE_CHANNEL_ID,
                message_id=channel_msg_id
            )
            delivered_count += 1
            await asyncio.sleep(0.35)  # Telegram FloodLimit himoyasi
        except TelegramForbiddenError:
            logger.warning(f"Foydalanuvchi {user_id} botni bloklagan. Xabarlarni qayta yuborish to'xtatildi.")
            break
        except TelegramBadRequest as e:
            logger.warning(f"Kanaldan xabarni nusxalashda xatolik (channel_msg_id={log.get('channel_msg_id')}): {e}")
            continue
        except Exception as e:
            logger.error(f"Xabarni tiklashda xatolik (channel_msg_id={log.get('channel_msg_id')}): {e}")

    await mark_archive_logs_delivered(user_id)
    if delivered_count > 0:
        if lang == "ru":
            done_text = f"✅ <b>{delivered_count} сохранённых сообщений успешно доставлены!</b>"
            if total > MAX_REPLAY:
                done_text += f"\n<i>(Показаны последние {MAX_REPLAY} из {total} сообщений)</i>"
        else:
            done_text = f"✅ <b>{delivered_count} ta saqlangan xabarlar muvaffaqiyatli yetkazildi!</b>"
            if total > MAX_REPLAY:
                done_text += f"\n<i>(Jami {total} tadan eng so'nggi {MAX_REPLAY} tasi ko'rsatildi)</i>"
        try:
            await bot.send_message(user_id, done_text, parse_mode="HTML")
        except Exception:
            pass

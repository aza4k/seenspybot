import html
import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from config import ADMIN_ID
from database import (
    get_user_snippet,
    set_user_snippet,
    delete_user_snippet,
    get_user_language,
    is_subscription_active,
)
from locales import get_text

logger = logging.getLogger(__name__)
router = Router(name="snippets_router")


class SnippetStates(StatesGroup):
    waiting_for_card = State()


def get_card_management_keyboard(lang: str, has_card: bool) -> InlineKeyboardMarkup:
    """Karta boshqaruvi uchun klaviatura."""
    buttons = []
    if has_card:
        buttons.append([
            InlineKeyboardButton(text=f"✏️ {get_text('btn_edit_card', lang)}", callback_data="snippet:edit_card"),
            InlineKeyboardButton(text=f"🗑 {get_text('btn_delete_card', lang)}", callback_data="snippet:delete_card"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text=f"💳 {get_text('btn_enter_card', lang)}", callback_data="snippet:edit_card")
        ])
    buttons.append([
        InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="back_to_menu")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def show_card_management(target: types.Message | types.CallbackQuery, user_id: int, lang: str, state: FSMContext, is_edit: bool = False):
    """Karta ma'lumotlari menyusini chiqarish."""
    await state.clear()
    card_text = await get_user_snippet(user_id, "card")
    has_card = bool(card_text)

    header = get_text("card_info_title", lang)
    if has_card:
        body = get_text("card_current", lang, card_text=html.escape(card_text))
    else:
        body = get_text("card_empty", lang)

    full_text = f"{header}{body}"
    kb = get_card_management_keyboard(lang, has_card)

    if isinstance(target, types.CallbackQuery):
        try:
            await target.message.edit_text(full_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await target.message.answer(full_text, reply_markup=kb, parse_mode="HTML")
        await target.answer()
    else:
        await target.answer(full_text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("card"))
@router.message(Command("karta"))
async def cmd_card(message: types.Message, state: FSMContext):
    """/card yoki /karta buyrug'i."""
    user_id = message.from_user.id
    lang = await get_user_language(user_id)
    parts = message.text.split(maxsplit=1)

    if len(parts) > 1 and parts[1].strip():
        card_content = parts[1].strip()
        await set_user_snippet(user_id, "card", card_content)
        await state.clear()
        res_text = get_text("card_saved_success", lang, card_text=html.escape(card_content))
        await message.answer(res_text, parse_mode="HTML")
        return

    await show_card_management(message, user_id, lang, state)


@router.callback_query(F.data == "snippet:manage_card")
async def cb_manage_card(call: types.CallbackQuery, state: FSMContext):
    """Menyudan karta boshqaruviga kirish."""
    user_id = call.from_user.id
    lang = await get_user_language(user_id)
    await show_card_management(call, user_id, lang, state, is_edit=True)


@router.callback_query(F.data == "snippet:edit_card")
async def cb_edit_card(call: types.CallbackQuery, state: FSMContext):
    """Karta kiritish / o'zgartirish so'rovi."""
    user_id = call.from_user.id
    lang = await get_user_language(user_id)
    await state.set_state(SnippetStates.waiting_for_card)

    prompt = get_text("card_prompt_enter", lang)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="snippet:manage_card")]
        ]
    )
    try:
        await call.message.edit_text(prompt, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await call.message.answer(prompt, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "snippet:delete_card")
async def cb_delete_card(call: types.CallbackQuery, state: FSMContext):
    """Kartani o'chirish."""
    user_id = call.from_user.id
    lang = await get_user_language(user_id)
    await delete_user_snippet(user_id, "card")
    await state.clear()

    del_text = get_text("card_deleted_success", lang)
    await call.answer(del_text, show_alert=True)
    await show_card_management(call, user_id, lang, state, is_edit=True)


@router.message(SnippetStates.waiting_for_card)
async def process_card_input(message: types.Message, state: FSMContext):
    """Foydalanuvchi yuborgan karta matnini saqlash."""
    user_id = message.from_user.id
    lang = await get_user_language(user_id)
    card_content = message.text.strip() if message.text else ""

    if not card_content:
        await message.answer("Iltimos, matn ko'rinishida karta raqamini yuboring:")
        return

    await set_user_snippet(user_id, "card", card_content)
    await state.clear()

    res_text = get_text("card_saved_success", lang, card_text=html.escape(card_content))
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="back_to_menu")]
        ]
    )
    await message.answer(res_text, reply_markup=kb, parse_mode="HTML")


@router.inline_query()
async def on_inline_query(query: InlineQuery):
    """Inline query (@seenspybot card) orqali guruhlarda kartani bitta bosish bilan yuborish."""
    user_id = query.from_user.id
    lang = await get_user_language(user_id)
    q_text = query.query.strip().lower()

    card_text = await get_user_snippet(user_id, "card")
    is_active = await is_subscription_active(user_id, ADMIN_ID)

    results = []

    if card_text and is_active:
        results.append(
            InlineQueryResultArticle(
                id="my_card",
                title="💳 Mening kartam" if lang == "uz" else "💳 Моя карта",
                description=card_text[:60],
                input_message_content=InputTextMessageContent(
                    message_text=card_text,
                    parse_mode="HTML"
                )
            )
        )
    elif not is_active:
        results.append(
            InlineQueryResultArticle(
                id="sub_expired",
                title="⚠️ Obunangiz tugagan" if lang == "uz" else "⚠️ Подписка истекла",
                description="Obunani yangilash uchun @seenspybot ga o'ting" if lang == "uz" else "Продлите подписку в @seenspybot",
                input_message_content=InputTextMessageContent(
                    message_text="⚠️ @seenspybot orqali obunani yangilang.",
                    parse_mode="HTML"
                )
            )
        )
    else:
        results.append(
            InlineQueryResultArticle(
                id="card_not_set",
                title="ℹ️ Karta kiritilmagan" if lang == "uz" else "ℹ️ Карта не сохранена",
                description="Kartani saqlash uchun @seenspybot ga o'ting" if lang == "uz" else "Сохраните карту через команду /card в @seenspybot",
                input_message_content=InputTextMessageContent(
                    message_text="ℹ️ Karta hali kiritilmagan. @seenspybot orqali /card buyrug'i bilan saqlang.",
                    parse_mode="HTML"
                )
            )
        )

    await query.answer(results=results, cache_time=1, is_personal=True)

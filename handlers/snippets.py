import html
import logging
import re
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
    get_all_user_snippets,
    get_user_snippets_count,
    get_user_language,
    is_subscription_active,
    ensure_free_trial,
)
from locales import get_text

logger = logging.getLogger(__name__)
router = Router(name="snippets_router")

MAX_SNIPPETS = 15


class SnippetStates(StatesGroup):
    waiting_for_keyword = State()
    waiting_for_content = State()


def clean_keyword(raw_kw: str) -> str:
    """Buyruq nomini tozalash (masalan: '.card' -> 'card')."""
    cleaned = raw_kw.strip().lstrip(".").lower()
    # Faqat lotin harflari, sonlar va pastki chiziq
    cleaned = re.sub(r"[^a-z0-9_]", "", cleaned)
    return cleaned


async def show_snippets_list(target: types.Message | types.CallbackQuery, user_id: int, lang: str, state: FSMContext):
    """Foydalanuvchining barcha tezkor javoblari ro'yxatini chiqarish."""
    if state:
        await state.clear()
    await ensure_free_trial(user_id)
    snippets = await get_all_user_snippets(user_id)
    count = len(snippets)

    title = get_text("quick_replies_title", lang)
    desc = get_text("quick_replies_desc", lang, count=count)

    if not snippets:
        body = get_text("quick_replies_empty", lang)
        full_text = f"{title}{desc}{body}"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=get_text("btn_add_quick_reply", lang), callback_data="snippet:add")],
                [InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="back_to_menu")]
            ]
        )
    else:
        list_lines = []
        snippet_buttons = []
        row = []
        for i, (kw, content) in enumerate(snippets.items(), 1):
            short_content = content[:35] + ("..." if len(content) > 35 else "")
            clean_short = html.escape(short_content).replace("\n", " ")
            list_lines.append(f"<b>{i}.</b> <code>.{kw}</code> ➔ <i>{clean_short}</i>")

            btn = InlineKeyboardButton(text=f".{kw}", callback_data=f"snippet:view:{kw}")
            row.append(btn)
            if len(row) == 2:
                snippet_buttons.append(row)
                row = []
        if row:
            snippet_buttons.append(row)

        full_text = f"{title}{desc}" + "\n".join(list_lines)

        control_buttons = []
        if count < MAX_SNIPPETS:
            control_buttons.append([InlineKeyboardButton(text=get_text("btn_add_quick_reply", lang), callback_data="snippet:add")])
        control_buttons.append([InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="back_to_menu")])

        kb = InlineKeyboardMarkup(inline_keyboard=snippet_buttons + control_buttons)

    if isinstance(target, types.CallbackQuery):
        try:
            await target.message.edit_text(full_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await target.message.answer(full_text, reply_markup=kb, parse_mode="HTML")
        await target.answer()
    else:
        await target.answer(full_text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "snippet:list")
async def cb_snippets_list(call: types.CallbackQuery, state: FSMContext):
    """Tezkor javoblar ro'yxatiga qaytish."""
    user_id = call.from_user.id
    lang = await get_user_language(user_id)
    await show_snippets_list(call, user_id, lang, state)


@router.message(Command("quick"))
@router.message(Command("snippets"))
async def cmd_quick(message: types.Message, state: FSMContext):
    """/quick yoki /snippets buyrug'i."""
    user_id = message.from_user.id
    lang = await get_user_language(user_id)
    parts = message.text.split(maxsplit=2)

    # Agar '/quick tel +99890...' shaklida birdaniga kiritilgan bo'lsa
    if len(parts) >= 3:
        kw = clean_keyword(parts[1])
        content = parts[2].strip()
        if not kw:
            await message.answer(get_text("quick_invalid_kw", lang), parse_mode="HTML")
            return

        count = await get_user_snippets_count(user_id)
        exists = await get_user_snippet(user_id, kw)
        if count >= MAX_SNIPPETS and not exists:
            await message.answer(get_text("quick_limit_reached", lang), parse_mode="HTML")
            return

        await set_user_snippet(user_id, kw, content)
        await state.clear()
        res_text = get_text("quick_saved_success", lang, kw=kw, content=html.escape(content))
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=get_text("btn_quick_replies", lang), callback_data="snippet:list")]
            ]
        )
        await message.answer(res_text, reply_markup=kb, parse_mode="HTML")
        return

    await show_snippets_list(message, user_id, lang, state)


@router.message(Command("card"))
@router.message(Command("karta"))
async def cmd_card_shortcut(message: types.Message, state: FSMContext):
    """/card yoki /karta uchun tezkor qisqartma."""
    user_id = message.from_user.id
    lang = await get_user_language(user_id)
    parts = message.text.split(maxsplit=1)

    if len(parts) > 1 and parts[1].strip():
        content = parts[1].strip()
        await set_user_snippet(user_id, "card", content)
        await state.clear()
        res_text = get_text("quick_saved_success", lang, kw="card", content=html.escape(content))
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=get_text("btn_quick_replies", lang), callback_data="snippet:list")]
            ]
        )
        await message.answer(res_text, reply_markup=kb, parse_mode="HTML")
        return

    # /card deb bo'sh yuborsa, to'g'ridan-to'g'ri card sozlamasini yoki ro'yxatni ko'rsatish
    card_content = await get_user_snippet(user_id, "card")
    if card_content:
        await show_single_snippet(message, user_id, "card", lang)
    else:
        # Darhol card kiritish bosqichiga o'tkazish
        await state.set_state(SnippetStates.waiting_for_content)
        await state.update_data(snippet_kw="card")
        prompt = get_text("quick_prompt_content", lang, kw="card")
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="snippet:list")]
            ]
        )
        await message.answer(prompt, reply_markup=kb, parse_mode="HTML")


async def show_single_snippet(target: types.Message | types.CallbackQuery, user_id: int, kw: str, lang: str):
    """Bitta buyruqni ko'rish va tahrirlash oynasi."""
    content = await get_user_snippet(user_id, kw)
    if not content:
        if isinstance(target, types.CallbackQuery):
            await show_snippets_list(target, user_id, lang, None)
        return

    text = get_text("quick_view_title", lang, kw=kw, content=html.escape(content))
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"✏️ {get_text('btn_edit_quick', lang)}", callback_data=f"snippet:edit:{kw}"),
                InlineKeyboardButton(text=f"🗑 {get_text('btn_delete_quick', lang)}", callback_data=f"snippet:del:{kw}"),
            ],
            [
                InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="snippet:list")
            ]
        ]
    )
    if isinstance(target, types.CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await target.message.answer(text, reply_markup=kb, parse_mode="HTML")
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("snippet:view:"))
async def cb_view_snippet(call: types.CallbackQuery, state: FSMContext):
    """Alohida buyruqni ko'rish."""
    user_id = call.from_user.id
    lang = await get_user_language(user_id)
    kw = call.data.split(":")[2]
    await state.clear()
    await show_single_snippet(call, user_id, kw, lang)


@router.callback_query(F.data == "snippet:add")
async def cb_add_snippet(call: types.CallbackQuery, state: FSMContext):
    """Yangi buyruq qo'shish boshlanishi."""
    user_id = call.from_user.id
    lang = await get_user_language(user_id)

    count = await get_user_snippets_count(user_id)
    if count >= MAX_SNIPPETS:
        await call.answer(get_text("quick_limit_reached", lang), show_alert=True)
        return

    await state.set_state(SnippetStates.waiting_for_keyword)
    prompt = get_text("quick_prompt_kw", lang)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="snippet:list")]
        ]
    )
    try:
        await call.message.edit_text(prompt, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await call.message.answer(prompt, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.message(SnippetStates.waiting_for_keyword)
async def process_keyword_input(message: types.Message, state: FSMContext):
    """Buyruq nomini qabul qilish (1-bosqich)."""
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    raw_text = message.text.strip() if message.text else ""
    kw = clean_keyword(raw_text)

    if not kw or len(kw) > 30:
        await message.answer(get_text("quick_invalid_kw", lang), parse_mode="HTML")
        return

    await state.update_data(snippet_kw=kw)
    await state.set_state(SnippetStates.waiting_for_content)

    prompt = get_text("quick_prompt_content", lang, kw=kw)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="snippet:list")]
        ]
    )
    await message.answer(prompt, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("snippet:edit:"))
async def cb_edit_snippet(call: types.CallbackQuery, state: FSMContext):
    """Mavjud buyruq matnini tahrirlash."""
    user_id = call.from_user.id
    lang = await get_user_language(user_id)
    kw = call.data.split(":")[2]

    await state.update_data(snippet_kw=kw)
    await state.set_state(SnippetStates.waiting_for_content)

    prompt = get_text("quick_prompt_content", lang, kw=kw)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text("btn_back", lang), callback_data=f"snippet:view:{kw}")]
        ]
    )
    try:
        await call.message.edit_text(prompt, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await call.message.answer(prompt, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.message(SnippetStates.waiting_for_content)
async def process_content_input(message: types.Message, state: FSMContext):
    """Buyruq matnini qabul qilish va saqlash (2-bosqich)."""
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    data = await state.get_data()
    kw = data.get("snippet_kw", "card")
    content = message.text.strip() if message.text else ""

    if not content:
        await message.answer("Iltimos, matn ko'rinishida yuboring:")
        return

    count = await get_user_snippets_count(user_id)
    exists = await get_user_snippet(user_id, kw)
    if count >= MAX_SNIPPETS and not exists:
        await state.clear()
        await message.answer(get_text("quick_limit_reached", lang), parse_mode="HTML")
        return

    await set_user_snippet(user_id, kw, content)
    await state.clear()

    res_text = get_text("quick_saved_success", lang, kw=kw, content=html.escape(content))
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text("btn_quick_replies", lang), callback_data="snippet:list")],
            [InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="back_to_menu")]
        ]
    )
    await message.answer(res_text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("snippet:del:"))
async def cb_delete_snippet(call: types.CallbackQuery, state: FSMContext):
    """Buyruqni o'chirish."""
    user_id = call.from_user.id
    lang = await get_user_language(user_id)
    kw = call.data.split(":")[2]

    await delete_user_snippet(user_id, kw)
    await state.clear()

    del_text = get_text("quick_deleted_success", lang, kw=kw)
    await call.answer(del_text, show_alert=True)
    await show_snippets_list(call, user_id, lang, state)


@router.inline_query()
async def on_inline_query(query: InlineQuery):
    """Inline query (@seenspybot [keyword]) orqali guruhlarda tezkor javoblarni yuborish."""
    user_id = query.from_user.id
    lang = await get_user_language(user_id)
    q_filter = query.query.strip().lstrip(".").lower()

    await ensure_free_trial(user_id)
    is_active = await is_subscription_active(user_id, ADMIN_ID)
    snippets = await get_all_user_snippets(user_id)

    results = []

    if not is_active:
        results.append(
            InlineQueryResultArticle(
                id="sub_expired",
                title="⚠️ Obunangiz tugagan" if lang == "uz" else "⚠️ Подписка истекла",
                description="Tezkor javoblardan foydalanish uchun @seenspybot da obunani yangilang" if lang == "uz" else "Продлите подписку в @seenspybot для использования быстрых ответов",
                input_message_content=InputTextMessageContent(
                    message_text="⚠️ @seenspybot orqali obunani yangilang.",
                    parse_mode="HTML"
                )
            )
        )
        await query.answer(results=results, cache_time=1, is_personal=True)
        return

    if not snippets:
        results.append(
            InlineQueryResultArticle(
                id="no_snippets",
                title="ℹ️ Tezkor javoblar mavjud emas" if lang == "uz" else "ℹ️ Нет сохранённых ответов",
                description="@seenspybot orqali /quick buyrug'i bilan buyruqlar qo'shing" if lang == "uz" else "Добавьте команды через /quick в @seenspybot",
                input_message_content=InputTextMessageContent(
                    message_text="ℹ️ @seenspybot orqali tezkor javoblarni saqlang.",
                    parse_mode="HTML"
                )
            )
        )
        await query.answer(results=results, cache_time=1, is_personal=True)
        return

    for kw, content in snippets.items():
        if q_filter and (q_filter not in kw and q_filter not in content.lower()):
            continue

        short_desc = content[:60].replace("\n", " ")
        results.append(
            InlineQueryResultArticle(
                id=f"quick_{kw}",
                title=f"⚡️ .{kw}",
                description=short_desc,
                input_message_content=InputTextMessageContent(
                    message_text=content,
                    parse_mode="HTML"
                )
            )
        )

    await query.answer(results=results[:50], cache_time=1, is_personal=True)

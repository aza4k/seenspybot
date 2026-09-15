import os
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from aiogram import Router, Bot, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from config import ADMIN_ID, DB_PATH
from database import (
    get_admin_detailed_stats,
    get_all_broadcast_users,
    get_user_full_profile,
    admin_add_subscription_days,
    admin_revoke_subscription,
    cleanup_old_messages,
    is_referral_enabled,
    set_referral_enabled,
    get_db_info,
    DB_ENGINE,
)


logger = logging.getLogger(__name__)
router = Router(name="admin_router")

MEDIA_DIR = Path("media_cache")


# FSM Holatlari
class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    confirm_send = State()


class UserManagerStates(StatesGroup):
    waiting_for_user_id = State()


def is_admin(user_id: int) -> bool:
    """Foydalanuvchi admin ekanligini tekshirish."""
    return user_id == ADMIN_ID


def get_admin_main_keyboard(is_ref_enabled: bool = True) -> InlineKeyboardMarkup:
    """Admin boshqaruv paneli tugmalari."""
    ref_text = "🟢 Referal: Yoqilgan" if is_ref_enabled else "🔴 Referal: O'chirilgan"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Batafsil Statistika", callback_data="admin:stats"),
                InlineKeyboardButton(text="📢 Xabar tarqatish", callback_data="admin:broadcast"),
            ],
            [
                InlineKeyboardButton(text="👤 Foydalanuvchini boshqarish", callback_data="admin:user_search"),
                InlineKeyboardButton(text="💾 Tizim va Kesh", callback_data="admin:system"),
            ],
            [
                InlineKeyboardButton(text=ref_text, callback_data="admin:toggle_referral"),
                InlineKeyboardButton(text="📥 Baza nusxasi", callback_data="admin:backup"),
            ],
            [
                InlineKeyboardButton(text="❌ Yopish", callback_data="admin:close"),
            ],
        ]
    )


@router.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    """Admin boshqaruv panelini ochish."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ <b>Kirish taqiqlangan!</b> Bu buyruq faqat bot administratori uchun.", parse_mode="HTML")
        return

    await state.clear()
    is_ref = await is_referral_enabled()
    text = (
        "👑 <b>Admin Boshqaruv Paneliga xush kelibsiz!</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )
    await message.answer(text, reply_markup=get_admin_main_keyboard(is_ref), parse_mode="HTML")


@router.callback_query(F.data == "admin:menu")
async def cb_admin_menu(call: types.CallbackQuery, state: FSMContext):
    """Admin bosh menyusiga qaytish."""
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ Ruxsat yo'q!", show_alert=True)
        return

    await state.clear()
    is_ref = await is_referral_enabled()
    text = (
        "👑 <b>Admin Boshqaruv Paneli:</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )
    try:
        await call.message.edit_text(text, reply_markup=get_admin_main_keyboard(is_ref), parse_mode="HTML")
    except Exception:
        await call.message.answer(text, reply_markup=get_admin_main_keyboard(is_ref), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "admin:toggle_referral")
async def cb_admin_toggle_referral(call: types.CallbackQuery):
    """Referal tizimini yoqish yoki o'chirish."""
    if not is_admin(call.from_user.id):
        return

    current = await is_referral_enabled()
    new_val = not current
    await set_referral_enabled(new_val)

    status_str = "yoqildi ✅" if new_val else "o'chirildi 🔴"
    await call.answer(f"Referal tizimi {status_str}", show_alert=True)

    kb = get_admin_main_keyboard(new_val)
    try:
        await call.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass


@router.callback_query(F.data == "admin:close")
async def cb_admin_close(call: types.CallbackQuery, state: FSMContext):
    """Admin panelni yopish."""
    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer("Panel yopildi.")


# -------------------------------------------------------------
# 1. BATAFSIL STATISTIKA
# -------------------------------------------------------------
@router.callback_query(F.data == "admin:stats")
async def cb_admin_stats(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    stats = await get_admin_detailed_stats()

    text = (
        "📊 <b>Botning Kengaytirilgan Statistikasi:</b>\n\n"
        f"👥 <b>Jami unikal foydalanuvchilar:</b> {stats['total_users']} ta\n"
        f"🔌 <b>Faol Business ulanishlar:</b> {stats['active_conns']} ta\n\n"
        "💬 <b>Xabarlar xotirasi:</b>\n"
        f"• Jami saqlangan: <b>{stats['total_msgs']} ta</b>\n"
        f"• Media fayllar: <b>{stats['total_media']} ta</b>\n\n"
        '<tg-emoji emoji-id="5388909270316114329">⭐️</tg-emoji> <b>Obunalar taqsimoti:</b>\n'
        f'• <tg-emoji emoji-id="5193085063998224234">🎁</tg-emoji> Faol Free Trial (30 kun): <b>{stats["active_trials"]} ta</b>\n'
        f"• 🟢 Faol to'lovli obunachilar: <b>{stats['active_paid']} ta</b>\n"
        f"• ⏳ Obuna muddati tugaganlar: <b>{stats['expired_count']} ta</b>\n\n"
        f'💰 <b>Jami tushgan daromad:</b> <tg-emoji emoji-id="5388909270316114329">⭐️</tg-emoji> <b>{stats["total_stars"]} Stars</b>\n\n'
        "📦 <b>Arxiv kanali ko'rsatkichlari:</b>\n"
        f"• Jami arxivlangan: <b>{stats['total_archive']} ta</b>\n"
        f"• To'lov kutilayotgan (ochilmagan): <b>{stats['undelivered_archive']} ta</b>"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin:stats")],
            [InlineKeyboardButton(text="🔙 Ortga", callback_data="admin:menu")],
        ]
    )
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await call.answer()


# -------------------------------------------------------------
# 2. XABAR TARQATISH (BROADCAST / RASSILKA)
# -------------------------------------------------------------
@router.callback_query(F.data == "admin:broadcast")
async def cb_admin_broadcast_start(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return

    await state.set_state(BroadcastStates.waiting_for_message)
    text = (
        "📢 <b>Xabar Tarqatish (Rassilka) Bo'limi</b>\n\n"
        "Barcha bot foydalanuvchilariga yubormoqchi bo'lgan xabaringizni yuboring.\n"
        "<i>(Matn, rasm, video, fayl, post yoki tugmali xabar yuborishingiz mumkin)</i>\n\n"
        "Bekor qilish uchun /cancel buyrug'ini yuboring."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚫 Bekor qilish", callback_data="broadcast:cancel")]
        ]
    )
    await call.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "broadcast:cancel")
@router.message(Command("cancel"))
async def cb_broadcast_cancel(event: types.Message | types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        msg_text = "🚫 <b>Jarayon bekor qilindi.</b>"
        if isinstance(event, types.CallbackQuery):
            await event.message.answer(msg_text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")
            await event.answer()
        else:
            await event.answer(msg_text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")


@router.message(BroadcastStates.waiting_for_message)
async def process_broadcast_message(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    # Xabar ID sini saqlash
    await state.update_data(broadcast_chat_id=message.chat.id, broadcast_msg_id=message.message_id)
    await state.set_state(BroadcastStates.confirm_send)

    users = await get_all_broadcast_users()
    total_users = len(users)

    text = (
        "👁 <b>Yuqoridagi xabar ko'rinishi barchaga yuboriladi.</b>\n\n"
        f"👥 Qabul qiluvchilar soni: <b>{total_users} ta foydalanuvchi</b>\n\n"
        "Rassilkani boshlashni tasdiqlaysizmi?"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Ha, yuborilsin!", callback_data="broadcast:confirm")],
            [InlineKeyboardButton(text="🚫 Bekor qilish", callback_data="broadcast:cancel")],
        ]
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(BroadcastStates.confirm_send, F.data == "broadcast:confirm")
async def cb_broadcast_confirm(call: types.CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(call.from_user.id):
        return

    data = await state.get_data()
    from_chat_id = data.get("broadcast_chat_id")
    msg_id = data.get("broadcast_msg_id")
    await state.clear()

    users = await get_all_broadcast_users()
    total = len(users)

    progress_msg = await call.message.answer(f"⏳ <b>Xabar tarqatilmoqda...</b> (0 / {total})", parse_mode="HTML")
    await call.answer()

    success_count = 0
    blocked_count = 0
    error_count = 0

    for idx, uid in enumerate(users, start=1):
        try:
            await bot.copy_message(
                chat_id=uid,
                from_chat_id=from_chat_id,
                message_id=msg_id
            )
            success_count += 1
        except TelegramForbiddenError:
            blocked_count += 1
        except TelegramBadRequest as e:
            error_count += 1
            logger.warning(f"Rassilka xatosi (uid={uid}): {e}")
        except Exception as e:
            error_count += 1
            logger.error(f"Kutilmagan xatolik (uid={uid}): {e}")

        # Telegram Flood limit himoyasi (har 20 tadan so'ng biroz kutish)
        if idx % 20 == 0:
            try:
                await progress_msg.edit_text(
                    f"⏳ <b>Xabar tarqatilmoqda...</b> ({idx} / {total})",
                    parse_mode="HTML"
                )
            except Exception:
                pass
            await asyncio.sleep(0.3)
        else:
            await asyncio.sleep(0.04)

    report_text = (
        "✅ <b>Xabar tarqatish muvaffaqiyatli yakunlandi!</b>\n\n"
        f"📊 <b>Natijalar:</b>\n"
        f"• Jami: <b>{total} ta</b>\n"
        f"• Yetkazildi: <b>{success_count} ta</b>\n"
        f"• Bloklaganlar: <b>{blocked_count} ta</b>\n"
        f"• Boshqa xatoliklar: <b>{error_count} ta</b>"
    )
    await progress_msg.edit_text(report_text, reply_markup=get_admin_main_keyboard(), parse_mode="HTML")


# -------------------------------------------------------------
# 3. FOYDALANUVCHILARNI BOSHQARISH (USER MANAGEMENT)
# -------------------------------------------------------------
@router.callback_query(F.data == "admin:user_search")
async def cb_user_search(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return

    await state.set_state(UserManagerStates.waiting_for_user_id)
    text = (
        "👤 <b>Foydalanuvchini Qidirish:</b>\n\n"
        "Foydalanuvchining Telegram <b>ID raqamini</b> kiriting (masalan: <code>7971120512</code>):\n\n"
        "Bekor qilish: /cancel"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Ortga", callback_data="admin:menu")]
        ]
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.message(UserManagerStates.waiting_for_user_id)
async def process_user_id_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    val = message.text.strip()
    if not val.isdigit():
        await message.answer("⚠️ Iltimos, faqat raqamlardan iborat Telegram ID kiriting:")
        return

    user_id = int(val)
    await state.clear()
    await send_user_card(message, user_id)


async def send_user_card(message: types.Message, user_id: int):
    """Foydalanuvchi kartochkasini chiqarish."""
    profile = await get_user_full_profile(user_id)
    sub = profile.get("subscription")
    conn = profile.get("connection")
    lang = profile.get("language", "ru")
    undelivered = profile.get("undelivered_count", 0)

    # Obuna ma'lumotlari
    now = datetime.now()
    if sub and sub.get("expires_at"):
        exp_str = sub["expires_at"]
        try:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S")
            if exp_date > now:
                days_left = (exp_date - now).days
                sub_status = f"🟢 Faol ({days_left} kun qoldi, <code>{exp_str}</code> gacha)"
            else:
                days_ago = (now - exp_date).days
                sub_status = f"🔴 Tugagan ({days_ago} kun oldin, <code>{exp_str}</code>)"
        except Exception:
            sub_status = f"Noma'lum ({exp_str})"
    else:
        sub_status = "⚪️ Obuna mavjud emas"

    # Ulanish holati
    if conn and conn.get("is_enabled"):
        conn_status = "🟢 Telegram Business ulangan"
    else:
        conn_status = "⚪️ Ulanmagan"

    card_text = (
        f"👤 <b>Foydalanuvchi Kartochkasi:</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"🌐 Tanlagan tili: <b>{'🇷🇺 Ruscha' if lang == 'ru' else '🇺🇿 O\'zbekcha'}</b>\n"
        f"🔌 Ulanish: <b>{conn_status}</b>\n"
        f"⭐️ Obuna: {sub_status}\n"
        f"📦 To'lovsiz arxivlangan xabarlar: <b>{undelivered} ta</b>\n\n"
        "Quyidagi amallardan birini tanlang:"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ 7 kun qo'shish", callback_data=f"uadd:7:{user_id}"),
                InlineKeyboardButton(text="➕ 30 kun qo'shish", callback_data=f"uadd:30:{user_id}"),
            ],
            [
                InlineKeyboardButton(text="➕ 1 Yil qo'shish", callback_data=f"uadd:365:{user_id}"),
                InlineKeyboardButton(text="🚫 Obunani bekor qilish", callback_data=f"urevoke:{user_id}"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="admin:menu")
            ]
        ]
    )
    await message.answer(card_text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("uadd:"))
async def cb_user_add_days(call: types.CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return

    parts = call.data.split(":")
    days = int(parts[1])
    user_id = int(parts[2])

    new_exp = await admin_add_subscription_days(user_id, days)
    await call.answer(f"✅ +{days} kun qo'shildi!", show_alert=True)

    # Foydalanuvchiga xabar yuborish
    try:
        await bot.send_message(
            user_id,
            f"🎁 <b>Admin tomonidan obunangizga +{days} kun taqdim etildi!</b>\n"
            f"Yangi amal qilish muddati: <code>{new_exp}</code> gacha.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await send_user_card(call.message, user_id)


@router.callback_query(F.data.startswith("urevoke:"))
async def cb_user_revoke(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    user_id = int(call.data.split(":")[1])
    await admin_revoke_subscription(user_id)
    await call.answer("🚫 Obuna bekor qilindi!", show_alert=True)
    await send_user_card(call.message, user_id)


# -------------------------------------------------------------
# 4. TIZIM VA KESH BOSHQARUVI
# -------------------------------------------------------------
@router.callback_query(F.data == "admin:system")
async def cb_admin_system(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    # 1. DB ma'lumotlari
    db_info = await get_db_info()
    db_engine_name = db_info.get("engine", "SQLite")
    db_size_str = db_info.get("size_str", "0.0 MB")

    # 2. Media kesh hajmi
    cache_files_count = 0
    cache_size_mb = 0.0
    if MEDIA_DIR.exists():
        for f in MEDIA_DIR.glob("*"):
            if f.is_file():
                cache_files_count += 1
                cache_size_mb += f.stat().st_size / (1024 * 1024)

    text = (
        "💾 <b>Tizim Xotirasi va Fayllar Holati:</b>\n\n"
        f"🗄 <b>Baza turi:</b> <code>{db_engine_name}</code>\n"
        f"📊 <b>Baza hajmi:</b> <code>{db_size_str}</code>\n"
        f"📁 <b>Media kesh papkasi:</b> <code>{cache_size_mb:.2f} MB</code> ({cache_files_count} ta fayl)\n\n"
        "💡 <i>Eslatma: Barcha o'chirilgan xabarlar shaxsiy arxiv kanalida saqlangan bo'lsa, "
        "1 haftadan (7 kundan) eski lokal kesh fayllarini xavfsiz tozalash mumkin.</i>"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧹 1 haftadan eski keshni tozalash", callback_data="admin:clean_cache")],
            [InlineKeyboardButton(text="📥 Baza zaxirasini yuklab olish", callback_data="admin:backup")],
            [InlineKeyboardButton(text="🔙 Ortga", callback_data="admin:menu")],
        ]
    )
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data == "admin:clean_cache")
async def cb_clean_cache(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    deleted_count = 0
    freed_mb = 0.0
    cutoff_time = datetime.now() - timedelta(days=7)

    if MEDIA_DIR.exists():
        for f in MEDIA_DIR.glob("*"):
            if f.is_file():
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime < cutoff_time:
                    size = f.stat().st_size
                    try:
                        f.unlink()
                        deleted_count += 1
                        freed_mb += size / (1024 * 1024)
                    except Exception:
                        pass

    # Shuningdek bazadagi 1 haftadan (7 kundan) eski xabarlarni tozalash
    await cleanup_old_messages(days=7)

    msg = f"🧹 <b>Kesh tozalandi:</b>\n{deleted_count} ta eski fayl o'chirildi, {freed_mb:.2f} MB joy bo'shatildi!"
    await call.answer(f"{deleted_count} ta fayl o'chirildi ({freed_mb:.2f} MB)", show_alert=True)
    await cb_admin_system(call)


@router.callback_query(F.data == "admin:backup")
async def cb_backup_db(call: types.CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return

    await call.answer("📥 Baza zaxirasi tayyorlanmoqda...")
    try:
        if DB_ENGINE == "sqlite":
            if not os.path.exists(DB_PATH):
                await call.message.answer("❌ SQLite baza fayli topilmadi!")
                return
            doc = FSInputFile(DB_PATH, filename=f"spyware_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
            await bot.send_document(
                chat_id=call.from_user.id,
                document=doc,
                caption=f"📦 <b>SQLite WAL Baza zaxirasi</b>\nSana: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                parse_mode="HTML"
            )
        else:
            # PostgreSQL: Export summary JSON
            from database import get_admin_detailed_stats, get_all_broadcast_users
            import json
            stats = await get_admin_detailed_stats()
            users = await get_all_broadcast_users()
            backup_data = {
                "engine": "PostgreSQL",
                "timestamp": datetime.now().isoformat(),
                "stats": stats,
                "users_count": len(users),
                "user_ids": users
            }
            tmp_path = Path(f"backup_pg_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            tmp_path.write_text(json.dumps(backup_data, indent=2, ensure_ascii=False), encoding="utf-8")
            doc = FSInputFile(str(tmp_path), filename=tmp_path.name)
            await bot.send_document(
                chat_id=call.from_user.id,
                document=doc,
                caption=f"🐘 <b>PostgreSQL Baza statistikasi va Userlar ro'yxati</b>\nSana: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                parse_mode="HTML"
            )
            try:
                tmp_path.unlink()
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Backup yuborishda xatolik: {e}")
        await call.message.answer(f"❌ Backup yuborishda xatolik: {e}")


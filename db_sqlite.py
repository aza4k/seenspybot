import aiosqlite
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from config import DB_PATH

logger = logging.getLogger(__name__)

_db_conn: Optional[aiosqlite.Connection] = None


async def get_db() -> aiosqlite.Connection:
    """Doimiy yuqori tezlikdagi ma'lumotlar bazasi ulanishini olish (WAL rejimi bilan)."""
    global _db_conn
    if _db_conn is None:
        _db_conn = await aiosqlite.connect(DB_PATH)
        _db_conn.row_factory = aiosqlite.Row
        
        # Yuqori yuklama (High Throughput) uchun optimizatsiyalar:
        await _db_conn.execute("PRAGMA journal_mode = WAL;")        # Write-Ahead Logging (o'qish va yozish parallel)
        await _db_conn.execute("PRAGMA synchronous = NORMAL;")       # Xotiraga tezkor yozish
        await _db_conn.execute("PRAGMA cache_size = 10000;")         # 10 000 sahifalik RAM kesh
        await _db_conn.execute("PRAGMA temp_store = MEMORY;")        # Vaqtinchalik jadvallarni RAM da saqlash
        await _db_conn.commit()
    return _db_conn


async def close_db():
    """Bot to'xtaganda bazani xavfsiz yopish."""
    global _db_conn
    if _db_conn is not None:
        await _db_conn.close()
        _db_conn = None


async def init_db():
    """Ma'lumotlar bazasi jadvallarini va indekslarini yaratish."""
    db = await get_db()
    
    await db.execute("""
        CREATE TABLE IF NOT EXISTS business_connections (
            connection_id TEXT PRIMARY KEY,
            user_id INTEGER,
            user_chat_id INTEGER,
            is_enabled INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    await db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id TEXT,
            chat_id INTEGER,
            chat_title TEXT,
            message_id INTEGER,
            sender_id INTEGER,
            sender_name TEXT,
            sender_username TEXT,
            is_from_me INTEGER DEFAULT 0,
            content_type TEXT,
            text TEXT,
            file_id TEXT,
            file_path TEXT,
            created_at TEXT,
            UNIQUE(chat_id, message_id)
        );
    """)

    # Telegram Stars Obunalari jadvali
    await db.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            expires_at TEXT,
            plan_type TEXT,
            stars_paid INTEGER,
            is_trial_used INTEGER DEFAULT 0,
            is_expired_notified INTEGER DEFAULT 0,
            is_cutoff_notified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Yangi ustunlar uchun xavfsiz migratsiya
    for col in ["is_trial_used", "is_expired_notified", "is_cutoff_notified"]:
        try:
            await db.execute(f"ALTER TABLE subscriptions ADD COLUMN {col} INTEGER DEFAULT 0;")
        except Exception:
            pass

    # Shaxsiy Kanal Arxiv jadvali
    await db.execute("""
        CREATE TABLE IF NOT EXISTS archive_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            chat_id INTEGER,
            channel_msg_id INTEGER,
            event_type TEXT,
            is_delivered INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_archive_user 
        ON archive_logs(user_id, is_delivered);
    """)
    
    # Tezkor qidiruv uchun indeks
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_msg 
        ON messages(chat_id, message_id);
    """)

    # 1 martalik / ushlangan medialarni qayta yubormaslik uchun jadval
    await db.execute("""
        CREATE TABLE IF NOT EXISTS captured_media (
            chat_id INTEGER,
            message_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (chat_id, message_id)
        );
    """)

    # Foydalanuvchi sozlamalari (Til va h.k.)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'ru',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Tizim sozlamalari (Referal yoqilgan/o'chirilgan)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Referal tizimi jadvali (Maksimal 7 ta taklif, ulanishda +1 kun)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_user_id INTEGER UNIQUE,
            is_connected INTEGER DEFAULT 0,
            reward_granted INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            connected_at TIMESTAMP
        );
    """)

    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_ref_referrer ON referrals(referrer_id);
    """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_ref_referred ON referrals(referred_user_id);
    """)
    
    # Avval qo'shilgan 7 kunlik Free Trial userlarini 30 kunga (1 oy) uzaytirish
    from datetime import datetime, timedelta
    new_trial_exp = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute("""
        UPDATE subscriptions
        SET expires_at = ?, updated_at = CURRENT_TIMESTAMP
        WHERE plan_type = 'free_trial' AND expires_at < ?;
    """, (new_trial_exp, new_trial_exp))

    await db.commit()


async def is_referral_enabled() -> bool:
    """Referal tizimi yoqilganligini tekshirish."""
    db = await get_db()
    async with db.execute("SELECT value FROM system_settings WHERE key = 'referral_enabled'") as cur:
        row = await cur.fetchone()
        if row:
            return row["value"] == "1"
    return True  # Default: yoqilgan


async def set_referral_enabled(enabled: bool) -> None:
    """Referal tizimini yoqish yoki o'chirish."""
    val = "1" if enabled else "0"
    db = await get_db()
    await db.execute("""
        INSERT INTO system_settings (key, value, updated_at)
        VALUES ('referral_enabled', ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
    """, (val,))
    await db.commit()


async def register_referral(referrer_id: int, referred_user_id: int) -> bool:
    """Yangi referalni ro'yxatga olish (Agar limit oshmagan va o'zini chaqirmagan bo'lsa)."""
    if referrer_id == referred_user_id:
        return False

    if not await is_referral_enabled():
        return False

    db = await get_db()

    # Avval boshqa birov tomonidan taklif qilinganmi yoki o'zi ro'yxatdan o'tganmi?
    async with db.execute("SELECT 1 FROM referrals WHERE referred_user_id = ?", (referred_user_id,)) as cur:
        if await cur.fetchone():
            return False

    # Taklif qiluvchining amaldagi takliflar soni 7 taga yetganmi?
    async with db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (referrer_id,)) as cur:
        count = (await cur.fetchone())[0]
        if count >= 7:
            return False

    await db.execute("""
        INSERT OR IGNORE INTO referrals (referrer_id, referred_user_id, is_connected, reward_granted)
        VALUES (?, ?, 0, 0)
    """, (referrer_id, referred_user_id))
    await db.commit()
    logger.info(f"🎁 Yangi referal bog'landi: Referrer={referrer_id} ➔ Do'st={referred_user_id}")
    return True


async def process_referral_connection_reward(referred_user_id: int) -> Optional[tuple[int, str]]:
    """Taklif qilingan do'st botni profiliga ulaganida, taklif qilganga +1 kun berish."""
    if not await is_referral_enabled():
        return None

    db = await get_db()
    async with db.execute("""
        SELECT referrer_id, reward_granted FROM referrals 
        WHERE referred_user_id = ?
    """, (referred_user_id,)) as cur:
        row = await cur.fetchone()

    if not row:
        return None

    referrer_id = row["referrer_id"]
    reward_granted = row["reward_granted"]

    if reward_granted:
        return None  # Mukofot avval berilgan

    # Taklif qiluvchining olgan mukofotlari soni 7 tadan kamligini tekshirish
    async with db.execute("""
        SELECT COUNT(*) FROM referrals 
        WHERE referrer_id = ? AND reward_granted = 1
    """, (referrer_id,)) as cur:
        rewards_count = (await cur.fetchone())[0]
        if rewards_count >= 7:
            return None

    # +1 kun qo'shish
    new_exp = await admin_add_subscription_days(referrer_id, 1)

    await db.execute("""
        UPDATE referrals 
        SET is_connected = 1, reward_granted = 1, connected_at = CURRENT_TIMESTAMP
        WHERE referred_user_id = ?
    """, (referred_user_id,))
    await db.commit()

    logger.info(f"🎉 Referal mukofoti berildi! Referrer={referrer_id} ga +1 kun (yangi muddat: {new_exp})")
    return (referrer_id, new_exp)


async def get_user_referral_stats(user_id: int) -> Dict[str, Any]:
    """Foydalanuvchining referal statistikasini olish."""
    db = await get_db()
    
    # Jami taklif qilinganlar
    async with db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,)) as cur:
        total_invited = (await cur.fetchone())[0]

    # Botni muvaffaqiyatli ulaganlar (mukofot olinganlar)
    async with db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND reward_granted = 1", (user_id,)) as cur:
        total_connected = (await cur.fetchone())[0]

    max_limit = 7
    remaining_slots = max(0, max_limit - total_invited)

    return {
        "total_invited": total_invited,
        "total_connected": total_connected,
        "max_limit": max_limit,
        "remaining_slots": remaining_slots,
        "reward_days": total_connected,
    }


async def get_user_language(user_id: int) -> str:
    """Foydalanuvchi tanlagan tilni olish (Birlamchi: 'ru')."""
    db = await get_db()
    async with db.execute(
        "SELECT language FROM user_settings WHERE user_id = ?",
        (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if row and row["language"]:
            return row["language"]
    return "ru"


async def set_user_language(user_id: int, language: str) -> None:
    """Foydalanuvchi tilini saqlash."""
    lang = language if language in ["ru", "uz"] else "ru"
    db = await get_db()
    await db.execute("""
        INSERT INTO user_settings (user_id, language, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            language = excluded.language,
            updated_at = CURRENT_TIMESTAMP
    """, (user_id, lang))
    await db.commit()


async def is_media_already_captured(chat_id: int, message_id: int) -> bool:
    """Media avval ushlangan yoki foydalanuvchiga yuborilganligini tekshirish."""
    db = await get_db()
    async with db.execute(
        "SELECT 1 FROM captured_media WHERE chat_id = ? AND message_id = ?",
        (chat_id, message_id)
    ) as cursor:
        row = await cursor.fetchone()
        return row is not None


async def mark_media_as_captured(chat_id: int, message_id: int) -> None:
    """Mediani ushlandi deb belgilash."""
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO captured_media (chat_id, message_id) VALUES (?, ?)",
        (chat_id, message_id)
    )
    await db.commit()



async def ensure_free_trial(user_id: int) -> bool:
    """Yangi foydalanuvchiga 30 kunlik (1 oy) Free Trial (bepul sinov) berish."""
    db = await get_db()
    async with db.execute(
        "SELECT user_id, is_trial_used FROM subscriptions WHERE user_id = ?",
        (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if row:
            return False  # Avval ro'yxatdan o'tgan
            
    from datetime import datetime, timedelta
    trial_expiry = datetime.now() + timedelta(days=30)
    expiry_str = trial_expiry.strftime("%Y-%m-%d %H:%M:%S")
    
    await db.execute("""
        INSERT INTO subscriptions (user_id, expires_at, plan_type, stars_paid, is_trial_used, updated_at)
        VALUES (?, ?, 'free_trial', 0, 1, CURRENT_TIMESTAMP)
    """, (user_id, expiry_str))
    await db.commit()
    logger.info(f"🎁 Yangi user {user_id} ga 30 kunlik Free Trial berildi: {expiry_str}")
    return True


async def get_user_subscription_status(user_id: int, admin_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Foydalanuvchi obunasining to'liq holati:
    - is_active: hozir faolmi (trial yoki pullik)
    - is_expired: muddati tugaganmi
    - days_since_expiry: muddati tugaganiga necha kun bo'ldi (1 oydan oshganini bilish uchun)
    """
    if admin_id and user_id == admin_id:
        return {
            "is_active": True,
            "is_expired": False,
            "days_since_expiry": 0,
            "plan_type": "admin",
            "expires_at": "Cheksiz (Admin)"
        }

    db = await get_db()
    async with db.execute(
        "SELECT expires_at, plan_type, is_trial_used FROM subscriptions WHERE user_id = ?",
        (user_id,)
    ) as cursor:
        row = await cursor.fetchone()

    if not row:
        # Yangi foydalanuvchi: Hech qachon ro'yxatdan o'tmagan bo'lsa, bir zumda 30 kunlik Free Trial beriladi!
        await ensure_free_trial(user_id)
        from datetime import datetime, timedelta
        trial_expiry = datetime.now() + timedelta(days=30)
        expiry_str = trial_expiry.strftime("%Y-%m-%d %H:%M:%S")
        return {
            "is_active": True,
            "is_expired": False,
            "days_since_expiry": 0,
            "plan_type": "free_trial",
            "expires_at": expiry_str
        }

    from datetime import datetime
    expires_at_str = row[0]
    if not expires_at_str:
        return {
            "is_active": False,
            "is_expired": True,
            "days_since_expiry": 999,
            "plan_type": "none",
            "expires_at": None
        }

    try:
        exp_date = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        if now < exp_date:
            return {
                "is_active": True,
                "is_expired": False,
                "days_since_expiry": 0,
                "plan_type": row[1],
                "expires_at": expires_at_str
            }
        else:
            days_expired = (now - exp_date).days
            return {
                "is_active": False,
                "is_expired": True,
                "days_since_expiry": days_expired,
                "plan_type": row[1],
                "expires_at": expires_at_str
            }
    except Exception:
        return {
            "is_active": False,
            "is_expired": True,
            "days_since_expiry": 999,
            "plan_type": row[1],
            "expires_at": expires_at_str
        }


async def save_archive_log(user_id: int, chat_id: int, channel_msg_id: int, event_type: str, is_delivered: bool):
    """Kanaldagi xabar ID sini arxiv logiga saqlash."""
    db = await get_db()
    await db.execute("""
        INSERT INTO archive_logs (user_id, chat_id, channel_msg_id, event_type, is_delivered)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, chat_id, channel_msg_id, event_type, 1 if is_delivered else 0))
    await db.commit()


async def get_undelivered_archive_logs(user_id: int) -> list:
    """Foydalanuvchiga hali yetkazilmagan kanaldagi xabarlar ro'yxati."""
    db = await get_db()
    async with db.execute("""
        SELECT channel_msg_id, event_type, created_at 
        FROM archive_logs 
        WHERE user_id = ? AND is_delivered = 0
        ORDER BY id ASC
    """, (user_id,)) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def mark_archive_logs_delivered(user_id: int):
    """Barcha to'plangan xabarlarni yetkazilgan deb belgilash."""
    db = await get_db()
    await db.execute("""
        UPDATE archive_logs 
        SET is_delivered = 1 
        WHERE user_id = ? AND is_delivered = 0
    """, (user_id,))
    await db.commit()


async def count_undelivered_messages(user_id: int) -> int:
    """Foydalanuvchining to'planib turgan (ochilmagan) xabarlari soni."""
    db = await get_db()
    async with db.execute("""
        SELECT COUNT(*) FROM archive_logs 
        WHERE user_id = ? AND is_delivered = 0
    """, (user_id,)) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_unnotified_expired_users() -> list:
    """Obunasi tugagan, lekin hali ogohlantirilmagan foydalanuvchilar."""
    db = await get_db()
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with db.execute("""
        SELECT user_id, expires_at 
        FROM subscriptions 
        WHERE expires_at < ? AND is_expired_notified = 0
    """, (now_str,)) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def mark_expired_notified(user_id: int):
    """Foydalanuvchiga obuna tugagani haqida bildirishnoma yuborilganini belgilash."""
    db = await get_db()
    await db.execute("""
        UPDATE subscriptions 
        SET is_expired_notified = 1 
        WHERE user_id = ?
    """, (user_id,))
    await db.commit()


async def get_unnotified_cutoff_users() -> list:
    """Obunasi tugaganiga 30 kundan oshgan, lekin hali uzilgani haqida ogohlantirilmaganlar."""
    db = await get_db()
    from datetime import datetime, timedelta
    cutoff_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    async with db.execute("""
        SELECT user_id, expires_at 
        FROM subscriptions 
        WHERE expires_at < ? AND is_cutoff_notified = 0
    """, (cutoff_date,)) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def mark_cutoff_notified(user_id: int):
    """Foydalanuvchiga 30 kunlik limit bo'yicha uzilgani bildirilganini belgilash."""
    db = await get_db()
    await db.execute("""
        UPDATE subscriptions 
        SET is_cutoff_notified = 1 
        WHERE user_id = ?
    """, (user_id,))
    await db.commit()


async def is_subscription_active(user_id: int, admin_id: Optional[int] = None) -> bool:
    """Foydalanuvchining faol obunasi bor-yo'qligini tekshirish."""
    status = await get_user_subscription_status(user_id, admin_id)
    return status["is_active"]



async def add_subscription(user_id: int, days: int, plan_type: str, stars_paid: int) -> str:
    """Obunani yangilash yoki mavjud muddat ustiga qo'shish."""
    from datetime import datetime, timedelta
    db = await get_db()
    
    current_expiry = None
    async with db.execute(
        "SELECT expires_at FROM subscriptions WHERE user_id = ?",
        (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if row and row[0]:
            try:
                exp = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                if exp > datetime.now():
                    current_expiry = exp
            except Exception:
                pass
                
    base_time = current_expiry if current_expiry else datetime.now()
    new_expiry = base_time + timedelta(days=days)
    new_expiry_str = new_expiry.strftime("%Y-%m-%d %H:%M:%S")
    
    await db.execute("""
        INSERT INTO subscriptions (user_id, expires_at, plan_type, stars_paid, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            expires_at = excluded.expires_at,
            plan_type = excluded.plan_type,
            stars_paid = subscriptions.stars_paid + excluded.stars_paid,
            is_expired_notified = 0,
            is_cutoff_notified = 0,
            updated_at = CURRENT_TIMESTAMP;
    """, (user_id, new_expiry_str, plan_type, stars_paid))
    await db.commit()
    
    return new_expiry_str


async def get_subscription_info(user_id: int) -> Optional[Dict[str, Any]]:
    """Foydalanuvchi obunasi tafsilotlari."""
    db = await get_db()
    async with db.execute(
        "SELECT expires_at, plan_type, stars_paid FROM subscriptions WHERE user_id = ?",
        (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if row:
            return {
                "expires_at": row[0],
                "plan_type": row[1],
                "stars_paid": row[2]
            }
    return None



async def save_connection(connection_id: str, user_id: int, user_chat_id: int, is_enabled: bool):
    """Business ulanish ma'lumotlarini saqlash."""
    db = await get_db()
    await db.execute("""
        INSERT INTO business_connections (connection_id, user_id, user_chat_id, is_enabled, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(connection_id) DO UPDATE SET
            user_id = excluded.user_id,
            user_chat_id = excluded.user_chat_id,
            is_enabled = excluded.is_enabled,
            updated_at = CURRENT_TIMESTAMP;
    """, (connection_id, user_id, user_chat_id, 1 if is_enabled else 0))
    await db.commit()


async def get_connection_owner_chat(connection_id: Optional[str] = None) -> Optional[int]:
    """Ulanish egasining Telegram chat_id sini tezkor olish."""
    db = await get_db()
    if connection_id:
        async with db.execute(
            "SELECT user_chat_id FROM business_connections WHERE connection_id = ?",
            (connection_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
    
    async with db.execute(
        "SELECT user_chat_id FROM business_connections WHERE is_enabled = 1 ORDER BY updated_at DESC LIMIT 1"
    ) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else None


async def save_message(
    connection_id: str,
    chat_id: int,
    chat_title: str,
    message_id: int,
    sender_id: int,
    sender_name: str,
    sender_username: str,
    is_from_me: bool,
    content_type: str,
    text: Optional[str],
    file_id: Optional[str] = None,
    file_path: Optional[str] = None,
    created_at: Optional[str] = None
):
    """Tezkor xabar yozish (UPSERT)."""
    db = await get_db()
    await db.execute("""
        INSERT INTO messages (
            connection_id, chat_id, chat_title, message_id,
            sender_id, sender_name, sender_username, is_from_me,
            content_type, text, file_id, file_path, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(chat_id, message_id) DO UPDATE SET
            text = excluded.text,
            file_id = excluded.file_id,
            file_path = COALESCE(excluded.file_path, messages.file_path),
            created_at = excluded.created_at;
    """, (
        connection_id, chat_id, chat_title, message_id,
        sender_id, sender_name, sender_username, 1 if is_from_me else 0,
        content_type, text or "", file_id, file_path, created_at
    ))
    await db.commit()


async def update_message_file_path(chat_id: int, message_id: int, file_path: str):
    """Yuklab olingan fayl yo'lini keshga yangilash."""
    db = await get_db()
    await db.execute("""
        UPDATE messages 
        SET file_path = ? 
        WHERE chat_id = ? AND message_id = ?
    """, (file_path, chat_id, message_id))
    await db.commit()


async def get_message(chat_id: int, message_id: int) -> Optional[Dict[str, Any]]:
    """Xabarni chat_id va message_id bo'yicha bazadan bir zumda olish."""
    db = await get_db()
    async with db.execute("""
        SELECT * FROM messages WHERE chat_id = ? AND message_id = ?
    """, (chat_id, message_id)) as cursor:
        row = await cursor.fetchone()
        if row:
            return dict(row)
    return None


async def update_message_text(chat_id: int, message_id: int, new_text: str):
    """Tahrirlangan xabar matnini yangilash."""
    db = await get_db()
    await db.execute("""
        UPDATE messages 
        SET text = ? 
        WHERE chat_id = ? AND message_id = ?
    """, (new_text, chat_id, message_id))
    await db.commit()


async def cleanup_old_messages(days: int = 3):
    """Eski xabarlarni tozalash (bazani yengil va tez saqlash uchun)."""
    try:
        db = await get_db()
        await db.execute("""
            DELETE FROM messages 
            WHERE created_at < datetime('now', ?)
        """, (f"-{days} days",))
        await db.commit()
    except Exception as e:
        logger.error(f"Eski xabarlarni tozalashda xatolik: {e}")


async def get_stats() -> Dict[str, Any]:
    """Statistikani olish."""
    db = await get_db()
    async with db.execute("SELECT COUNT(*) FROM messages") as cursor:
        total_msgs = (await cursor.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM messages WHERE file_path IS NOT NULL") as cursor:
        total_media = (await cursor.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM business_connections WHERE is_enabled = 1") as cursor:
        active_conns = (await cursor.fetchone())[0]
    return {
        "total_messages": total_msgs,
        "total_media": total_media,
        "active_connections": active_conns
    }


async def get_admin_detailed_stats() -> Dict[str, Any]:
    """Admin uchun to'liq kengaytirilgan statistikani olish."""
    db = await get_db()
    
    # 1. Jami unikal userlar
    async with db.execute("""
        SELECT COUNT(DISTINCT uid) FROM (
            SELECT user_id as uid FROM subscriptions
            UNION
            SELECT user_id as uid FROM user_settings
            UNION
            SELECT user_chat_id as uid FROM business_connections WHERE user_chat_id IS NOT NULL
        )
    """) as cur:
        total_users = (await cur.fetchone())[0]

    # 2. Faol biznes ulanishlar
    async with db.execute("SELECT COUNT(*) FROM business_connections WHERE is_enabled = 1") as cur:
        active_conns = (await cur.fetchone())[0]

    # 3. Jami xabarlar va media
    async with db.execute("SELECT COUNT(*) FROM messages") as cur:
        total_msgs = (await cur.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM messages WHERE content_type != 'text'") as cur:
        total_media = (await cur.fetchone())[0]

    # 4. Obunalar statistikasi
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with db.execute("SELECT COUNT(*) FROM subscriptions WHERE plan_type = 'free_trial' AND expires_at > ?", (now_str,)) as cur:
        active_trials = (await cur.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM subscriptions WHERE plan_type != 'free_trial' AND expires_at > ?", (now_str,)) as cur:
        active_paid = (await cur.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM subscriptions WHERE expires_at <= ?", (now_str,)) as cur:
        expired_count = (await cur.fetchone())[0]

    # 5. Jami tushgan Stars
    async with db.execute("SELECT COALESCE(SUM(stars_paid), 0) FROM subscriptions") as cur:
        total_stars = (await cur.fetchone())[0]

    # 6. Arxiv loglari
    async with db.execute("SELECT COUNT(*) FROM archive_logs WHERE is_delivered = 0") as cur:
        undelivered_archive = (await cur.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM archive_logs") as cur:
        total_archive = (await cur.fetchone())[0]

    return {
        "total_users": total_users,
        "active_conns": active_conns,
        "total_msgs": total_msgs,
        "total_media": total_media,
        "active_trials": active_trials,
        "active_paid": active_paid,
        "expired_count": expired_count,
        "total_stars": total_stars,
        "undelivered_archive": undelivered_archive,
        "total_archive": total_archive,
    }


async def get_all_broadcast_users() -> List[int]:
    """Rassilka yuborish uchun barcha unikal user_id larni olish."""
    db = await get_db()
    async with db.execute("""
        SELECT DISTINCT uid FROM (
            SELECT user_id as uid FROM subscriptions
            UNION
            SELECT user_id as uid FROM user_settings
            UNION
            SELECT user_chat_id as uid FROM business_connections WHERE user_chat_id IS NOT NULL
        )
    """) as cur:
        rows = await cur.fetchall()
        return [r[0] for r in rows if r[0]]


async def get_user_full_profile(user_id: int) -> Dict[str, Any]:
    """Bitta foydalanuvchining to'liq profil ma'lumotlarini olish."""
    db = await get_db()
    
    # Sub
    async with db.execute("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)) as cur:
        sub = await cur.fetchone()
        sub_dict = dict(sub) if sub else None

    # Connection
    async with db.execute("SELECT * FROM business_connections WHERE user_id = ? OR user_chat_id = ?", (user_id, user_id)) as cur:
        conn = await cur.fetchone()
        conn_dict = dict(conn) if conn else None

    # Language
    async with db.execute("SELECT language FROM user_settings WHERE user_id = ?", (user_id,)) as cur:
        lang_row = await cur.fetchone()
        language = lang_row["language"] if lang_row else "ru"

    # Undelivered logs
    async with db.execute("SELECT COUNT(*) FROM archive_logs WHERE user_id = ? AND is_delivered = 0", (user_id,)) as cur:
        undelivered = (await cur.fetchone())[0]

    return {
        "user_id": user_id,
        "subscription": sub_dict,
        "connection": conn_dict,
        "language": language,
        "undelivered_count": undelivered,
    }


async def admin_add_subscription_days(user_id: int, days: int) -> str:
    """Admin tomonidan obunaga kun qo'shish."""
    db = await get_db()
    async with db.execute("SELECT expires_at FROM subscriptions WHERE user_id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
    
    now = datetime.now()
    if row and row["expires_at"]:
        try:
            current_exp = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
            start_date = max(now, current_exp)
        except Exception:
            start_date = now
    else:
        start_date = now

    new_exp = start_date + timedelta(days=days)
    new_exp_str = new_exp.strftime("%Y-%m-%d %H:%M:%S")

    await db.execute("""
        INSERT INTO subscriptions (user_id, expires_at, plan_type, stars_paid, is_trial_used, is_expired_notified, is_cutoff_notified, updated_at)
        VALUES (?, ?, 'admin_grant', 0, 1, 0, 0, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            expires_at = excluded.expires_at,
            plan_type = 'admin_grant',
            is_expired_notified = 0,
            is_cutoff_notified = 0,
            updated_at = CURRENT_TIMESTAMP
    """, (user_id, new_exp_str))
    await db.commit()
    return new_exp_str


async def admin_revoke_subscription(user_id: int) -> None:
    """Admin tomonidan obunani zudlik bilan bekor qilish."""
    db = await get_db()
    now_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute("""
        UPDATE subscriptions 
        SET expires_at = ?, plan_type = 'revoked', updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
    """, (now_str, user_id))
    await db.commit()


async def get_db_info() -> Dict[str, Any]:
    """Baza turi va hajmi haqida ma'lumot."""
    import os
    size_bytes = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    size_mb = size_bytes / (1024 * 1024)
    return {
        "engine": "SQLite (WAL)",
        "size_str": f"{size_mb:.2f} MB"
    }


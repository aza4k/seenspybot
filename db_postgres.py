import asyncpg
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from config import DATABASE_URL

logger = logging.getLogger(__name__)

_pg_pool: Optional[asyncpg.Pool] = None


async def get_pg_pool() -> asyncpg.Pool:
    """PostgreSQL ulanishlar puli (Connection Pool)."""
    global _pg_pool
    if _pg_pool is None:
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL aniqlanmadi! PostgreSQL ulanishi uchun DATABASE_URL ni belgilang.")
        logger.info("Connecting to PostgreSQL pool...")
        _pg_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=20,
            command_timeout=60
        )
        logger.info("✅ PostgreSQL connection pool muvaffaqiyatli yaratildi (min=2, max=20).")
    return _pg_pool


async def get_db() -> asyncpg.Pool:
    """Doimiy yuqori tezlikdagi PostgreSQL pool olish."""
    return await get_pg_pool()


async def close_db():
    """Bot to'xtaganda poolni xavfsiz yopish."""
    global _pg_pool
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None
        logger.info("PostgreSQL connection pool yopildi.")


async def init_db():
    """PostgreSQL jadvallari va indekslarini yaratish."""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        # 1. Business Connections
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS business_connections (
                connection_id TEXT PRIMARY KEY,
                user_id BIGINT,
                user_chat_id BIGINT,
                is_enabled INTEGER DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Messages (Telegram IDs can exceed 32-bit integer, using BIGINT)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id BIGSERIAL PRIMARY KEY,
                connection_id TEXT,
                chat_id BIGINT,
                chat_title TEXT,
                message_id BIGINT,
                sender_id BIGINT,
                sender_name TEXT,
                sender_username TEXT,
                is_from_me INTEGER DEFAULT 0,
                content_type TEXT,
                text TEXT,
                file_id TEXT,
                file_path TEXT,
                created_at TEXT,
                CONSTRAINT uq_chat_message UNIQUE(chat_id, message_id)
            );
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_msg ON messages(chat_id, message_id);
        """)

        # 3. Subscriptions
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id BIGINT PRIMARY KEY,
                expires_at TEXT,
                plan_type TEXT,
                stars_paid INTEGER DEFAULT 0,
                is_trial_used INTEGER DEFAULT 0,
                is_expired_notified INTEGER DEFAULT 0,
                is_cutoff_notified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 4. Archive logs
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS archive_logs (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT,
                chat_id BIGINT,
                channel_msg_id BIGINT,
                event_type TEXT,
                is_delivered INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_archive_user ON archive_logs(user_id, is_delivered);
        """)

        # 5. Captured media (TTL / View-Once)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS captured_media (
                chat_id BIGINT,
                message_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (chat_id, message_id)
            );
        """)

        # 6. User settings
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id BIGINT PRIMARY KEY,
                language TEXT DEFAULT 'ru',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 7. System settings
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 8. Referrals
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id BIGSERIAL PRIMARY KEY,
                referrer_id BIGINT,
                referred_user_id BIGINT UNIQUE,
                is_connected INTEGER DEFAULT 0,
                reward_granted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                connected_at TIMESTAMP
            );
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ref_referrer ON referrals(referrer_id);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ref_referred ON referrals(referred_user_id);
        """)

    logger.info("✅ PostgreSQL jadvallari va indekslari muvaffaqiyatli tekshirildi/yaratildi.")


async def is_referral_enabled() -> bool:
    """Referal tizimi yoqilganligini tekshirish."""
    pool = await get_pg_pool()
    val = await pool.fetchval("SELECT value FROM system_settings WHERE key = 'referral_enabled'")
    if val is not None:
        return val == "1"
    return True


async def set_referral_enabled(enabled: bool) -> None:
    """Referal tizimini yoqish yoki o'chirish."""
    val = "1" if enabled else "0"
    pool = await get_pg_pool()
    await pool.execute("""
        INSERT INTO system_settings (key, value, updated_at)
        VALUES ('referral_enabled', $1, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = EXCLUDED.value,
            updated_at = CURRENT_TIMESTAMP
    """, val)


async def register_referral(referrer_id: int, referred_user_id: int) -> bool:
    """Yangi referalni ro'yxatga olish (Agar limit oshmagan va o'zini chaqirmagan bo'lsa)."""
    if referrer_id == referred_user_id:
        return False

    if not await is_referral_enabled():
        return False

    pool = await get_pg_pool()

    # Avval boshqa birov tomonidan taklif qilinganmi yoki o'zi ro'yxatdan o'tganmi?
    exists = await pool.fetchval("SELECT 1 FROM referrals WHERE referred_user_id = $1", referred_user_id)
    if exists:
        return False

    # Taklif qiluvchining amaldagi takliflar soni 7 taga yetganmi?
    count = await pool.fetchval("SELECT COUNT(*) FROM referrals WHERE referrer_id = $1", referrer_id)
    if count and count >= 7:
        return False

    await pool.execute("""
        INSERT INTO referrals (referrer_id, referred_user_id, is_connected, reward_granted)
        VALUES ($1, $2, 0, 0)
        ON CONFLICT (referred_user_id) DO NOTHING
    """, referrer_id, referred_user_id)
    logger.info(f"🎁 Yangi referal bog'landi: Referrer={referrer_id} ➔ Do'st={referred_user_id}")
    return True


async def process_referral_connection_reward(referred_user_id: int) -> Optional[tuple[int, str]]:
    """Taklif qilingan do'st botni profiliga ulaganida, taklif qilganga +1 kun berish."""
    if not await is_referral_enabled():
        return None

    pool = await get_pg_pool()
    row = await pool.fetchrow("""
        SELECT referrer_id, reward_granted FROM referrals 
        WHERE referred_user_id = $1
    """, referred_user_id)

    if not row:
        return None

    referrer_id = row["referrer_id"]
    reward_granted = row["reward_granted"]

    if reward_granted:
        return None  # Mukofot avval berilgan

    rewards_count = await pool.fetchval("""
        SELECT COUNT(*) FROM referrals 
        WHERE referrer_id = $1 AND reward_granted = 1
    """, referrer_id)
    if rewards_count and rewards_count >= 7:
        return None

    new_exp = await admin_add_subscription_days(referrer_id, 1)

    await pool.execute("""
        UPDATE referrals 
        SET is_connected = 1, reward_granted = 1, connected_at = CURRENT_TIMESTAMP
        WHERE referred_user_id = $1
    """, referred_user_id)

    logger.info(f"🎉 Referal mukofoti berildi! Referrer={referrer_id} ga +1 kun (yangi muddat: {new_exp})")
    return (referrer_id, new_exp)


async def get_user_referral_stats(user_id: int) -> Dict[str, Any]:
    """Foydalanuvchining referal statistikasini olish."""
    pool = await get_pg_pool()
    total_invited = await pool.fetchval("SELECT COUNT(*) FROM referrals WHERE referrer_id = $1", user_id) or 0
    total_connected = await pool.fetchval("SELECT COUNT(*) FROM referrals WHERE referrer_id = $1 AND reward_granted = 1", user_id) or 0

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
    pool = await get_pg_pool()
    lang = await pool.fetchval("SELECT language FROM user_settings WHERE user_id = $1", user_id)
    return lang if lang else "ru"


async def set_user_language(user_id: int, language: str) -> None:
    """Foydalanuvchi tilini saqlash."""
    lang = language if language in ["ru", "uz"] else "ru"
    pool = await get_pg_pool()
    await pool.execute("""
        INSERT INTO user_settings (user_id, language, updated_at)
        VALUES ($1, $2, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            language = EXCLUDED.language,
            updated_at = CURRENT_TIMESTAMP
    """, user_id, lang)


async def is_media_already_captured(chat_id: int, message_id: int) -> bool:
    """Media avval ushlangan yoki foydalanuvchiga yuborilganligini tekshirish."""
    pool = await get_pg_pool()
    row = await pool.fetchrow(
        "SELECT 1 FROM captured_media WHERE chat_id = $1 AND message_id = $2",
        chat_id, message_id
    )
    return row is not None


async def mark_media_as_captured(chat_id: int, message_id: int) -> None:
    """Mediani ushlandi deb belgilash."""
    pool = await get_pg_pool()
    await pool.execute(
        "INSERT INTO captured_media (chat_id, message_id) VALUES ($1, $2) ON CONFLICT (chat_id, message_id) DO NOTHING",
        chat_id, message_id
    )


async def ensure_free_trial(user_id: int) -> bool:
    """Yangi foydalanuvchiga 7 kunlik Free Trial (bepul sinov) berish."""
    pool = await get_pg_pool()
    row = await pool.fetchrow(
        "SELECT user_id, is_trial_used FROM subscriptions WHERE user_id = $1",
        user_id
    )
    if row:
        return False

    trial_expiry = datetime.now() + timedelta(days=7)
    expiry_str = trial_expiry.strftime("%Y-%m-%d %H:%M:%S")

    await pool.execute("""
        INSERT INTO subscriptions (user_id, expires_at, plan_type, stars_paid, is_trial_used, updated_at)
        VALUES ($1, $2, 'free_trial', 0, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO NOTHING
    """, user_id, expiry_str)
    logger.info(f"🎁 Yangi user {user_id} ga 7 kunlik Free Trial berildi: {expiry_str}")
    return True


async def get_user_subscription_status(user_id: int, admin_id: Optional[int] = None) -> Dict[str, Any]:
    """Foydalanuvchi obunasining to'liq holati."""
    if admin_id and user_id == admin_id:
        return {
            "is_active": True,
            "is_expired": False,
            "days_since_expiry": 0,
            "plan_type": "admin",
            "expires_at": "Cheksiz (Admin)"
        }

    pool = await get_pg_pool()
    row = await pool.fetchrow(
        "SELECT expires_at, plan_type, is_trial_used FROM subscriptions WHERE user_id = $1",
        user_id
    )

    if not row:
        await ensure_free_trial(user_id)
        trial_expiry = datetime.now() + timedelta(days=7)
        expiry_str = trial_expiry.strftime("%Y-%m-%d %H:%M:%S")
        return {
            "is_active": True,
            "is_expired": False,
            "days_since_expiry": 0,
            "plan_type": "free_trial",
            "expires_at": expiry_str
        }

    expires_at_str = row["expires_at"]
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
                "plan_type": row["plan_type"],
                "expires_at": expires_at_str
            }
        else:
            days_expired = (now - exp_date).days
            return {
                "is_active": False,
                "is_expired": True,
                "days_since_expiry": days_expired,
                "plan_type": row["plan_type"],
                "expires_at": expires_at_str
            }
    except Exception:
        return {
            "is_active": False,
            "is_expired": True,
            "days_since_expiry": 999,
            "plan_type": row["plan_type"],
            "expires_at": expires_at_str
        }


async def save_archive_log(user_id: int, chat_id: int, channel_msg_id: int, event_type: str, is_delivered: bool):
    """Kanaldagi xabar ID sini arxiv logiga saqlash."""
    pool = await get_pg_pool()
    await pool.execute("""
        INSERT INTO archive_logs (user_id, chat_id, channel_msg_id, event_type, is_delivered)
        VALUES ($1, $2, $3, $4, $5)
    """, user_id, chat_id, channel_msg_id, event_type, 1 if is_delivered else 0)


async def get_undelivered_archive_logs(user_id: int) -> list:
    """Foydalanuvchiga hali yetkazilmagan kanaldagi xabarlar ro'yxati."""
    pool = await get_pg_pool()
    rows = await pool.fetch("""
        SELECT channel_msg_id, event_type, created_at 
        FROM archive_logs 
        WHERE user_id = $1 AND is_delivered = 0
        ORDER BY id ASC
    """, user_id)
    return [dict(row) for row in rows]


async def mark_archive_logs_delivered(user_id: int):
    """Barcha to'plangan xabarlarni yetkazilgan deb belgilash."""
    pool = await get_pg_pool()
    await pool.execute("""
        UPDATE archive_logs 
        SET is_delivered = 1 
        WHERE user_id = $1 AND is_delivered = 0
    """, user_id)


async def count_undelivered_messages(user_id: int) -> int:
    """Foydalanuvchining to'planib turgan (ochilmagan) xabarlari soni."""
    pool = await get_pg_pool()
    val = await pool.fetchval("""
        SELECT COUNT(*) FROM archive_logs 
        WHERE user_id = $1 AND is_delivered = 0
    """, user_id)
    return val or 0


async def get_unnotified_expired_users() -> list:
    """Obunasi tugagan, lekin hali ogohlantirilmagan foydalanuvchilar."""
    pool = await get_pg_pool()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = await pool.fetch("""
        SELECT user_id, expires_at 
        FROM subscriptions 
        WHERE expires_at < $1 AND is_expired_notified = 0
    """, now_str)
    return [dict(row) for row in rows]


async def mark_expired_notified(user_id: int):
    """Foydalanuvchiga obuna tugagani haqida bildirishnoma yuborilganini belgilash."""
    pool = await get_pg_pool()
    await pool.execute("""
        UPDATE subscriptions 
        SET is_expired_notified = 1 
        WHERE user_id = $1
    """, user_id)


async def get_unnotified_cutoff_users() -> list:
    """Obunasi tugaganiga 30 kundan oshgan, lekin hali uzilgani haqida ogohlantirilmaganlar."""
    pool = await get_pg_pool()
    cutoff_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    rows = await pool.fetch("""
        SELECT user_id, expires_at 
        FROM subscriptions 
        WHERE expires_at < $1 AND is_cutoff_notified = 0
    """, cutoff_date)
    return [dict(row) for row in rows]


async def mark_cutoff_notified(user_id: int):
    """Foydalanuvchiga 30 kunlik limit bo'yicha uzilgani bildirilganini belgilash."""
    pool = await get_pg_pool()
    await pool.execute("""
        UPDATE subscriptions 
        SET is_cutoff_notified = 1 
        WHERE user_id = $1
    """, user_id)


async def is_subscription_active(user_id: int, admin_id: Optional[int] = None) -> bool:
    """Foydalanuvchining faol obunasi bor-yo'qligini tekshirish."""
    status = await get_user_subscription_status(user_id, admin_id)
    return status["is_active"]


async def add_subscription(user_id: int, days: int, plan_type: str, stars_paid: int) -> str:
    """Obunani yangilash yoki mavjud muddat ustiga qo'shish."""
    pool = await get_pg_pool()
    current_expiry = None
    row = await pool.fetchrow(
        "SELECT expires_at FROM subscriptions WHERE user_id = $1",
        user_id
    )
    if row and row["expires_at"]:
        try:
            exp = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
            if exp > datetime.now():
                current_expiry = exp
        except Exception:
            pass

    base_time = current_expiry if current_expiry else datetime.now()
    new_expiry = base_time + timedelta(days=days)
    new_expiry_str = new_expiry.strftime("%Y-%m-%d %H:%M:%S")

    await pool.execute("""
        INSERT INTO subscriptions (user_id, expires_at, plan_type, stars_paid, updated_at)
        VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            expires_at = EXCLUDED.expires_at,
            plan_type = EXCLUDED.plan_type,
            stars_paid = subscriptions.stars_paid + EXCLUDED.stars_paid,
            is_expired_notified = 0,
            is_cutoff_notified = 0,
            updated_at = CURRENT_TIMESTAMP;
    """, user_id, new_expiry_str, plan_type, stars_paid)

    return new_expiry_str


async def get_subscription_info(user_id: int) -> Optional[Dict[str, Any]]:
    """Foydalanuvchi obunasi tafsilotlari."""
    pool = await get_pg_pool()
    row = await pool.fetchrow(
        "SELECT expires_at, plan_type, stars_paid FROM subscriptions WHERE user_id = $1",
        user_id
    )
    if row:
        return {
            "expires_at": row["expires_at"],
            "plan_type": row["plan_type"],
            "stars_paid": row["stars_paid"]
        }
    return None


async def save_connection(connection_id: str, user_id: int, user_chat_id: int, is_enabled: bool):
    """Business ulanish ma'lumotlarini saqlash."""
    pool = await get_pg_pool()
    await pool.execute("""
        INSERT INTO business_connections (connection_id, user_id, user_chat_id, is_enabled, updated_at)
        VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
        ON CONFLICT(connection_id) DO UPDATE SET
            user_id = EXCLUDED.user_id,
            user_chat_id = EXCLUDED.user_chat_id,
            is_enabled = EXCLUDED.is_enabled,
            updated_at = CURRENT_TIMESTAMP;
    """, connection_id, user_id, user_chat_id, 1 if is_enabled else 0)


async def get_connection_owner_chat(connection_id: Optional[str] = None) -> Optional[int]:
    """Ulanish egasining Telegram chat_id sini tezkor olish."""
    pool = await get_pg_pool()
    if connection_id:
        val = await pool.fetchval(
            "SELECT user_chat_id FROM business_connections WHERE connection_id = $1",
            connection_id
        )
        if val is not None:
            return val

    val = await pool.fetchval(
        "SELECT user_chat_id FROM business_connections WHERE is_enabled = 1 ORDER BY updated_at DESC LIMIT 1"
    )
    return val


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
    pool = await get_pg_pool()
    await pool.execute("""
        INSERT INTO messages (
            connection_id, chat_id, chat_title, message_id,
            sender_id, sender_name, sender_username, is_from_me,
            content_type, text, file_id, file_path, created_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        ON CONFLICT(chat_id, message_id) DO UPDATE SET
            text = EXCLUDED.text,
            file_id = EXCLUDED.file_id,
            file_path = COALESCE(EXCLUDED.file_path, messages.file_path),
            created_at = EXCLUDED.created_at;
    """,
        connection_id, chat_id, chat_title, message_id,
        sender_id, sender_name, sender_username, 1 if is_from_me else 0,
        content_type, text or "", file_id, file_path, created_at
    )


async def update_message_file_path(chat_id: int, message_id: int, file_path: str):
    """Yuklab olingan fayl yo'lini keshga yangilash."""
    pool = await get_pg_pool()
    await pool.execute("""
        UPDATE messages 
        SET file_path = $1 
        WHERE chat_id = $2 AND message_id = $3
    """, file_path, chat_id, message_id)


async def get_message(chat_id: int, message_id: int) -> Optional[Dict[str, Any]]:
    """Xabarni chat_id va message_id bo'yicha bazadan bir zumda olish."""
    pool = await get_pg_pool()
    row = await pool.fetchrow("""
        SELECT * FROM messages WHERE chat_id = $1 AND message_id = $2
    """, chat_id, message_id)
    return dict(row) if row else None


async def update_message_text(chat_id: int, message_id: int, new_text: str):
    """Tahrirlangan xabar matnini yangilash."""
    pool = await get_pg_pool()
    await pool.execute("""
        UPDATE messages 
        SET text = $1 
        WHERE chat_id = $2 AND message_id = $3
    """, new_text, chat_id, message_id)


async def cleanup_old_messages(days: int = 3):
    """Eski xabarlarni tozalash (bazani yengil va tez saqlash uchun)."""
    try:
        pool = await get_pg_pool()
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        await pool.execute("""
            DELETE FROM messages 
            WHERE created_at < $1
        """, cutoff)
    except Exception as e:
        logger.error(f"Eski xabarlarni tozalashda xatolik: {e}")


async def get_stats() -> Dict[str, Any]:
    """Statistikani olish."""
    pool = await get_pg_pool()
    total_msgs = await pool.fetchval("SELECT COUNT(*) FROM messages") or 0
    total_media = await pool.fetchval("SELECT COUNT(*) FROM messages WHERE file_path IS NOT NULL") or 0
    active_conns = await pool.fetchval("SELECT COUNT(*) FROM business_connections WHERE is_enabled = 1") or 0
    return {
        "total_messages": total_msgs,
        "total_media": total_media,
        "active_connections": active_conns
    }


async def get_admin_detailed_stats() -> Dict[str, Any]:
    """Admin uchun to'liq kengaytirilgan statistikani olish."""
    pool = await get_pg_pool()

    # 1. Jami unikal userlar
    total_users = await pool.fetchval("""
        SELECT COUNT(DISTINCT uid) FROM (
            SELECT user_id as uid FROM subscriptions
            UNION
            SELECT user_id as uid FROM user_settings
            UNION
            SELECT user_chat_id as uid FROM business_connections WHERE user_chat_id IS NOT NULL
        ) AS all_users
    """) or 0

    # 2. Faol biznes ulanishlar
    active_conns = await pool.fetchval("SELECT COUNT(*) FROM business_connections WHERE is_enabled = 1") or 0

    # 3. Jami xabarlar va media
    total_msgs = await pool.fetchval("SELECT COUNT(*) FROM messages") or 0
    total_media = await pool.fetchval("SELECT COUNT(*) FROM messages WHERE content_type != 'text'") or 0

    # 4. Obunalar statistikasi
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    active_trials = await pool.fetchval("""
        SELECT COUNT(*) FROM subscriptions WHERE plan_type = 'free_trial' AND expires_at > $1
    """, now_str) or 0
    active_paid = await pool.fetchval("""
        SELECT COUNT(*) FROM subscriptions WHERE plan_type != 'free_trial' AND expires_at > $1
    """, now_str) or 0
    expired_count = await pool.fetchval("""
        SELECT COUNT(*) FROM subscriptions WHERE expires_at <= $1
    """, now_str) or 0

    # 5. Jami tushgan Stars
    total_stars = await pool.fetchval("SELECT COALESCE(SUM(stars_paid), 0) FROM subscriptions") or 0

    # 6. Arxiv loglari
    undelivered_archive = await pool.fetchval("SELECT COUNT(*) FROM archive_logs WHERE is_delivered = 0") or 0
    total_archive = await pool.fetchval("SELECT COUNT(*) FROM archive_logs") or 0

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
    pool = await get_pg_pool()
    rows = await pool.fetch("""
        SELECT DISTINCT uid FROM (
            SELECT user_id as uid FROM subscriptions
            UNION
            SELECT user_id as uid FROM user_settings
            UNION
            SELECT user_chat_id as uid FROM business_connections WHERE user_chat_id IS NOT NULL
        ) AS all_users
    """)
    return [r["uid"] for r in rows if r["uid"]]


async def get_user_full_profile(user_id: int) -> Dict[str, Any]:
    """Bitta foydalanuvchining to'liq profil ma'lumotlarini olish."""
    pool = await get_pg_pool()

    sub = await pool.fetchrow("SELECT * FROM subscriptions WHERE user_id = $1", user_id)
    conn = await pool.fetchrow("SELECT * FROM business_connections WHERE user_id = $1 OR user_chat_id = $1", user_id)
    lang = await pool.fetchval("SELECT language FROM user_settings WHERE user_id = $1", user_id)
    undelivered = await pool.fetchval("SELECT COUNT(*) FROM archive_logs WHERE user_id = $1 AND is_delivered = 0", user_id) or 0

    return {
        "user_id": user_id,
        "subscription": dict(sub) if sub else None,
        "connection": dict(conn) if conn else None,
        "language": lang if lang else "ru",
        "undelivered_count": undelivered,
    }


async def admin_add_subscription_days(user_id: int, days: int) -> str:
    """Admin tomonidan obunaga kun qo'shish."""
    pool = await get_pg_pool()
    row = await pool.fetchrow("SELECT expires_at FROM subscriptions WHERE user_id = $1", user_id)

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

    await pool.execute("""
        INSERT INTO subscriptions (user_id, expires_at, plan_type, stars_paid, is_trial_used, is_expired_notified, is_cutoff_notified, updated_at)
        VALUES ($1, $2, 'admin_grant', 0, 1, 0, 0, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            expires_at = EXCLUDED.expires_at,
            plan_type = 'admin_grant',
            is_expired_notified = 0,
            is_cutoff_notified = 0,
            updated_at = CURRENT_TIMESTAMP
    """, user_id, new_exp_str)
    return new_exp_str


async def admin_revoke_subscription(user_id: int) -> None:
    """Admin tomonidan obunani zudlik bilan bekor qilish."""
    pool = await get_pg_pool()
    now_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    await pool.execute("""
        UPDATE subscriptions 
        SET expires_at = $1, plan_type = 'revoked', updated_at = CURRENT_TIMESTAMP
        WHERE user_id = $2
    """, now_str, user_id)


async def get_db_info() -> Dict[str, Any]:
    """Baza turi va hajmi haqida ma'lumot."""
    try:
        pool = await get_pg_pool()
        size_str = await pool.fetchval("SELECT pg_size_pretty(pg_database_size(current_database()))")
        return {
            "engine": "PostgreSQL (asyncpg Pool)",
            "size_str": size_str or "N/A"
        }
    except Exception as e:
        return {
            "engine": "PostgreSQL",
            "size_str": f"Ulanishda: {e}"
        }

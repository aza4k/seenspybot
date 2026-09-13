import os
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()
ADMIN_ID = int(ADMIN_ID_RAW) if ADMIN_ID_RAW.isdigit() else None

ARCHIVE_CHANNEL_RAW = os.getenv("ARCHIVE_CHANNEL_ID", "").strip()
ARCHIVE_CHANNEL_ID = int(ARCHIVE_CHANNEL_RAW) if ARCHIVE_CHANNEL_RAW.lstrip("-").isdigit() else None

DB_PATH = os.getenv("DB_PATH", "spyware.db")

# PostgreSQL URL (Railway, Supabase, Neon yoki mahalliy PostgreSQL uchun)
DATABASE_URL = (os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or "").strip()
if DATABASE_URL.startswith("postgres://"):
    # asyncpg va SQLAlchemy uchun postgresql:// prefiksi talab qilinadi
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

IS_POSTGRES = bool(DATABASE_URL and (DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")))

if not BOT_TOKEN:
    print("OGOHLANTIRISH: BOT_TOKEN aniqlanmadi! Iltimos, .env faylida BOT_TOKEN ni belgilang.")


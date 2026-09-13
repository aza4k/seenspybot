# 🕵️‍♂️ Telegram Seen Spy Bot (@seenspybot)

Telegram profilidagi o'chirilgan xabarlar (matn, rasm, video, ovozli xabar) hamda 1 martalik (View-Once / TTL) medialarni saqlab qoluvchi va foydalanuvchiga yetkazib beruvchi Telegram Business boti.

---

## 🚀 Asosiy Imkoniyatlar (Features)

1. **🗑 O'chirilgan xabarlarni tutib olish:**
   - Chatda suhbatdoshingiz xabarni "Delete for everyone" qilib o'chirib yuborsa ham, bot o'sha xabarning matni yoki media faylini (rasm, video, ovoz, yumaloq video, hujjat) zudlik bilan bot chatingizga yetkazadi.
2. **👁 1 marta ko'riladigan (View-Once) medialar:**
   - 1 martalik yuborilgan rasm va videolar o'chib ketishidan oldin avtomatik saqlab olinadi.
3. **🌐 Ikki tilli interfeys (RU / UZ):**
   - Asosiy til — rus tili, shuningdek o'zbek tiliga bitta tugma orqali o'tish imkoniyati.
4. **👥 7 kishilik Referal Tizimi:**
   - Har bir foydalanuvchi ko'pi bilan 7 nafar do'stini taklif qila oladi.
   - Do'sti botni o'z Telegram Business profiliga muvaffaqiyatli ulaganda, taklif qilganga +1 kun obuna beriladi.
5. **👑 Administrator Paneli (`/admin`):**
   - Foydalanuvchilar, ulangan biznes hisoblar va saqlangan xabarlar statistikasi.
   - Foydalanuvchini ID orqali qidirish, obunani uzaytirish yoki bekor qilish.
   - Ommaviy xabar yuborish (Broadcast) funksiyasi.
   - Referal tizimini yoqish/o'chirish sozlamasi.
   - SQLite ma'lumotlar bazasini to'g'ridan-to'g'ri botga yuklab olish (Backup).
   - Keshni tozalash funksiyasi.
6. **⚡️ Yuqori tezlik (WAL Rejimi):**
   - SQLite `WAL (Write-Ahead Logging)` va xotira keshida ishlaydi, soniyasiga minglab xabarlarni qulay qayta ishlaydi.

---

## 🚂 Railway Platformasiga Joylash (Deployment)

Loyiha Railway platformasida **Worker** sifatida ishlashga to'liq tayyorlangan (`Procfile` va `railway.json` mavjud).

### 1-qadam: Railway-da yangi loyiha ochish
1. [Railway.app](https://railway.app) ga kiring va GitHub profilingiz orqali tizimga kiring.
2. **"New Project"** -> **"Deploy from GitHub repo"** ni tanlang.
3. `aza4k/seenspybot` repozitoriyasini tanlang.

### 2-qadam: Muhit o'zgaruvchilarini sozlash (Variables)
Railway loyiha sozlamalarida **Variables** bo'limiga o'tib, quyidagi o'zgaruvchilarni qo'shing:

| O'zgaruvchi | Tavsif | Misol |
| :--- | :--- | :--- |
| `BOT_TOKEN` | @BotFather dan olingan bot tokeni | `862628...` |
| `ADMIN_ID` | Bot adminining Telegram ID raqami | `842321...` |
| `ARCHIVE_CHANNEL_ID` | (Ixtiyoriy) Saqlash uchun kanal ID | `-100...` |
| `DB_PATH` | Ma'lumotlar bazasi fayli yo'li | `spyware.db` |

> ⚠️ **Eslatma:** Hech qachon shaxsiy `.env` faylingizni GitHub-ga yuklamang! Barcha maxfiy kalitlar faqat Railway **Variables** qismida saqlanadi.

---

## 💻 Mahalliy Ishga Tushirish (Local Run)

```bash
# 1. Virtual muhit yaratish va faollashtirish
python -m venv venv
venv\Scripts\activate  # Windows

# 2. Kerakli paketlarni o'rnatish
pip install -r requirements.txt

# 3. .env faylini yaratish
cp .env.example .env
# .env fayliga o'z BOT_TOKEN va ADMIN_ID laringizni yozing

# 4. Botni ishga tushirish
python run.py
```

---

## 📁 Loyiha Tuzilmasi

```
├── handlers/              # Aiogram handlerlari (buyruqlar, admin, referal, biznes)
│   ├── admin.py           # Admin panel va boshqaruv funksiyalari
│   ├── business.py        # Telegram Business xabar va o'chirishlarni tutish
│   ├── common.py          # /start, /help, referal, til almashtirish
│   └── payments.py        # Obuna va to'lovlar
├── database.py            # SQLite WAL bazasi va optimallashgan so'rovlar
├── locales.py             # Rus va O'zbek tillari matnlari
├── config.py              # Konfiguratsiya va sozlamalar
├── scheduler.py           # Obunalarni tekshirish va eslatmalar
├── ttl_saver.py           # 1 martalik (View-Once) medialar saqlovchisi
├── run.py                 # Asosiy botni ishga tushirish fayli
├── Procfile               # Railway Worker konfiguratsiyasi
├── railway.json           # Railway deploy sozlamalari
└── requirements.txt       # Python kutubxonalari
```

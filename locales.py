"""
Ko'p tillilik (Localization) moduli: Ruscha (birlamchi) va O'zbekcha.
"""
from typing import Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import PRIVACY_POLICY_URL

# Birlamchi til

DEFAULT_LANGUAGE = "ru"

# Xabarlar lug'ati
MESSAGES: Dict[str, Dict[str, str]] = {
    "ru": {
        # Boshlang'ich xabarlar
        "trial_banner": "",
        "start_text": (
            "🎁 <b>Вам активирован бесплатный доступ на 7 дней!</b>\n\n"
            "Бот моментально сохраняет и присылает:\n"
            "• 🗑 <b>Удалённые</b> сообщения собеседника\n"
            "• ✏️ <b>Изменённые</b> сообщения (до и после)\n"
            "• 👁 <b>Одноразовые</b> фото и видео\n\n"
            "👇 Нажмите зелёную кнопку ниже для подключения:"
        ),
        "status_title": "📊 <b>Статус бота:</b> {status_icon}\n\n",
        "status_connections": "🔗 Подключений: <b>{active_connections} профилей</b>\n",
        "status_messages": "💬 Сообщений в памяти: <b>{total_messages}</b>\n",
        "status_subscription": "⭐ Ваша подписка: <b>{sub_status}</b>\n\n",
        "status_footer": "Бот отслеживает <b>удалённые</b> и <b>одноразовые</b> медиа.",
        
        # Sub status
        "sub_admin": "👑 Безлимитный Админ",
        "sub_active": "🟢 Активна ({plan_name}, до <code>{expires_at}</code>)",
        "sub_trial_name": "Бесплатный тест (7 дней)",
        "sub_inactive": "⚪️ Не активна",

        # Tugmalar
        "btn_connect": "🟢 Подключить бота",

        "btn_plans": "⭐ Подписка / Тарифы",
        "btn_stats": "📊 Статус",
        "btn_language": "🌐 Язык / Til",
        "btn_back": "🔙 Назад",
        "btn_referral": "🎁 Пригласить друзей (+дни)",
        "btn_privacy": "📄 Политика конфиденциальности",
        "privacy_text": (
            "📄 <b>Политика конфиденциальности (@seenspybot)</b>\n\n"
            "Сервис работает в строгом соответствии с регламентом <b>Telegram Business API</b>:\n\n"
            "• <b>Персональный доступ:</b> Все сохранённые копии удалённых сообщений доставляются исключительно вам.\n"
            "• <b>Временный кэш:</b> Данные буферизируются до 3 дней и автоматически удаляются.\n"
            "• <b>Полный контроль:</b> Вы можете в любой момент выбрать конкретные чаты или отключить бота в настройках Telegram.\n\n"
            "🌐 Полный текст политики конфиденциальности опубликован на веб-сайте:"
        ),


        # Referral
        "referral_title": "🎁 <b>Реферальная программа</b>\n\n",
        "referral_body": (
            "Приглашайте друзей в бота и получайте <b>+1 день полной подписки</b> за каждого друга, "
            "который подключит бота к своему профилю!\n\n"
            "📊 <b>Ваша статистика:</b>\n"
            "• Приглашено друзей: <b>{invited} / {max_limit}</b>\n"
            "• Подключили бота: <b>{connected} человек</b>\n"
            "• Получено бонусных дней: <b>+{reward_days} дней</b>\n"
            "• Осталось мест для приглашения: <b>{remaining} мест</b>\n\n"
            "🔗 <b>Ваша персональная ссылка:</b>\n<code>{ref_link}</code>\n\n"
            "⚠️ <i>Бонус начисляется сразу, как только ваш друг подключит бота через Telegram Business!</i>"
        ),
        "referral_disabled": "⚠️ <b>Реферальная программа временно отключена администратором.</b>",
        "referral_reward_notify": (
            "🎉 <b>Отличная новость!</b>\n\n"
            "Приглашённый вами друг подключил бота к своему профилю!\n"
            "Вам начислено: <b>+1 день подписки</b> 🎁\n"
            "Новый срок действия: <code>{expires_at}</code>."
        ),
        "btn_share_ref": "📲 Поделиться ссылкой",
        "share_text": "Привет! Попробуй этого бота для Telegram Business — он сохраняет удалённые сообщения и одноразовые фото/видео:",

        # Tilni o'zgartirish
        "choose_lang": "🌐 <b>Выберите язык интерфейса / Tilni tanlang:</b>",
        "lang_selected": "✅ <b>Язык успешно изменён на Русский!</b>",

        # Ulanish holati
        "conn_trial": (
            "\n\n🎁 <b>Вам активирован БЕСПЛАТНЫЙ ТЕСТ НА 7 ДНЕЙ!</b>\n"
            "В течение недели бот сохраняет абсолютно все удалённые и одноразовые медиа."
        ),
        "conn_success": (
            "✅ <b>Бот успешно подключён к вашему профилю!</b>\n\n"
            "👤 Профиль: <b>{user_name}</b>"
            "{trial_text}\n\n"
            "📖 <b>Как использовать?</b>\n"
            "➖ <b>Удалённые сообщения:</b> Если собеседник удалит сообщение, бот сразу пришлёт вам его копию (текст, фото, видео, голосовые).\n"
            "➖ <b>Изменённые сообщения:</b> Бот покажет старый и новый вариант текста.\n"
            "➖ <b>Одноразовые (с таймером) медиа:</b> Чтобы сохранить фото или видео с таймером, <b>до открытия</b> ответьте на него в диалоге любым сообщением (например точкой <code>.</code>). Бот сразу пришлёт его вам!\n\n"
            "❗️ <i>Примечание: бот фиксирует новые сообщения, полученные после подключения.</i>"
        ),
        "conn_disabled": (
            "⚠️ <b>Бот отключён от профиля!</b>\n\n"
            "👤 Профиль: {user_name}\n"
            "Отслеживание приостановлено."
        ),

        # Tahrirlangan xabar
        "msg_edited": (
            "✏️ <b>Сообщение изменено!</b>\n\n"
            "👤 <b>От:</b> {who} ({sender_name})\n"
            "👥 <b>Чат:</b> {chat_title}\n\n"
            "❌ <b>Старый текст:</b>\n<blockquote>{old_text}</blockquote>\n"
            "✅ <b>Новый текст:</b>\n<blockquote>{new_text}</blockquote>"
        ),

        # 1 martalik media
        "msg_view_once": (
            "👁 <b>Одноразовое (с таймером) медиа сохранено!</b>\n\n"
            "👤 <b>От:</b> {sender_name}\n"
            "💬 <b>Чат:</b> {chat_title}\n"
            "🕒 <b>Время:</b> {time_str}\n"
        ),
        "msg_view_once_footer": "\n🎯 <i>Вы ответили (Reply) на сообщение, поэтому бот сохранил его для вас!</i>",

        # O'chirilgan xabar
        "msg_deleted_title": "🗑 <b>Удалённое сообщение</b>\n\n",
        "msg_deleted_body": (
            "👤 <b>От:</b> {who} ({sender_name})\n"
            "👥 <b>Чат:</b> {chat_title}\n"
            "🕒 <b>Отправлено:</b> {sent_time}\n"
            "🗑 <b>Удалено:</b> {delete_time}\n\n"
        ),
        "promo_footer": (
            "\n\n➖➖➖➖➖➖➖➖➖➖\n"
            "🕵️‍♂️ <b>Сохранено через @seenspybot</b>\n"
            "👉 <i>Узнай, что удаляют в твоих чатах!</i>"
        ),


        # Teaserlar (obunasi yo'q foydalanuvchilar uchun)
        "teaser_deleted_title": "🔒 <b>У вас новое удалённое сообщение!</b>\n\n",
        "teaser_deleted_body": (
            "Кто-то только что удалил сообщение в ваших чатах.\n"
            "Оно надёжно сохранено в архиве.\n"
            "📦 Всего пропущенных сообщений: <b>{total_missed} шт.</b>\n\n"
            "Чтобы увидеть их, активируйте подписку!\n"
            "👉 Нажмите кнопку ниже или введите команду /buy."
        ),
        "teaser_view_once": (
            "🔒 <b>У вас новое одноразовое медиа!</b>\n\n"
            "В ваших чатах перехвачено фото/видео с таймером и надёжно заархивировано.\n"
            "📦 Всего пропущенных сообщений: <b>{total_missed} шт.</b>\n\n"
            "Чтобы просмотреть и сохранить его, активируйте подписку!\n"
            "👉 Нажмите кнопку ниже или введите команду /buy."
        ),
        "btn_unlock": "🔓 Посмотреть сообщения ({total_missed} шт.)",

        # Tariflar va to'lovlar
        "plans_title": (
            "⭐️ <b>Тарифные планы подписки</b>\n\n"
            "Выберите подходящий период для доступа ко всем удалённым сообщениям и одноразовым медиа:\n\n"
            "• <b>1 Неделя</b> — 5 Stars\n"
            "• <b>1 Месяц</b> — 15 Stars <i>(Скидка 25%)</i>\n"
            "• <b>1 Год</b> — 180 Stars <i>(Самый выгодный)</i>\n\n"
            "Оплата производится безопасно через официальные <b>Telegram Stars</b> ⭐"
        ),
        "plan_week_name": "1 Неделя (7 дней)",
        "plan_week_desc": "Доступ к удалённым и одноразовым сообщениям на 7 дней",
        "plan_month_name": "1 Месяц (30 дней)",
        "plan_month_desc": "Доступ к удалённым и одноразовым сообщениям на 30 дней (Выгодно)",
        "plan_year_name": "1 Год (365 дней)",
        "plan_year_desc": "Доступ к удалённым и одноразовым сообщениям на 365 дней (Максимальная выгода)",
        "invoice_title": "Подписка: {plan_name}",
        "payment_success": (
            "🎉 <b>Оплата прошла успешно!</b>\n\n"
            "⭐️ Тариф: <b>{plan_name}</b>\n"
            "⏳ Действует до: <code>{expires_at}</code>\n\n"
            "Спасибо за подписку! Все функции бота полностью активны."
        ),
        "payment_replay_header": (
            "📦 <b>Восстановление архива:</b>\n"
            "Пока у вас не было подписки, накопилось <b>{count} сообщений</b>. "
            "Отправляем их вам прямо сейчас:\n"
        ),

        # Scheduler xabarnomalari
        "scheduler_expired": (
            "⏳ <b>Срок вашей подписки истёк!</b>\n\n"
            "Ваша подписка завершена (Время окончания: <code>{exp_date}</code>).\n\n"
            "Чтобы продолжать видеть удалённые и одноразовые сообщения, продлите подписку.\n\n"
            "📦 <i>Не переживайте, все новые удалённые сообщения надёжно сохраняются в архиве и будут доставлены вам сразу после оплаты!</i>\n\n"
            "👉 Нажмите кнопку ниже или используйте команду /buy."
        ),
        "btn_renew_sub": "⭐ Продлить подписку",
        "scheduler_cutoff": (
            "⚠️ <b>С момента окончания подписки прошло более 30 дней!</b>\n\n"
            "Так как подписка не обновлялась в течение месяца, сохранение новых удалённых сообщений приостановлено.\n\n"
            "Чтобы возобновить работу сервиса и сохранение архива, активируйте подписку.\n\n"
            "👉 Для продления: /buy"
        ),
    },
    "uz": {
        # Boshlang'ich xabarlar
        "trial_banner": "",
        "start_text": (
            "🎁 <b>7 kunlik bepul sinov muddati faollashtirildi!</b>\n\n"
            "Bot darhol saqlab, sizga yetkazadi:\n"
            "• 🗑 <b>O'chirilgan</b> xabarlar nusxasi\n"
            "• ✏️ <b>Tahrirlangan</b> xabarlar tarixi\n"
            "• 👁 <b>1 martalik</b> rasm va videolar\n\n"
            "👇 Ulanish uchun quyidagi yashil tugmani bosing:"
        ),

        "status_title": "📊 <b>Bot Holati:</b> {status_icon}\n\n",
        "status_connections": "🔗 Ulanishlar: <b>{active_connections} ta profil</b>\n",
        "status_messages": "💬 Xotiradagi xabarlar: <b>{total_messages} ta</b>\n",
        "status_subscription": "⭐ Obunangiz: <b>{sub_status}</b>\n\n",
        "status_footer": "Faqat <b>o'chirilgan</b> va <b>1 martalik</b> xabarlar ushlanadi.",
        
        # Sub status
        "sub_admin": "👑 Cheksiz Admin",
        "sub_active": "🟢 Faol ({plan_name}, <code>{expires_at}</code> gacha)",
        "sub_trial_name": "Free Trial (7 kun)",
        "sub_inactive": "⚪️ Faol emas",

        # Tugmalar
        "btn_connect": "🟢 Botni ulash",

        "btn_plans": "⭐ Obuna / Tariflar",
        "btn_stats": "📊 Statistika",
        "btn_language": "🌐 Til / Язык",
        "btn_back": "🔙 Orqaga",
        "btn_referral": "🎁 Do'stlarni taklif qilish (+kunlar)",
        "btn_privacy": "📄 Maxfiylik siyosati",
        "privacy_text": (
            "📄 <b>Maxfiylik siyosati (@seenspybot)</b>\n\n"
            "Xizmat rasmiy <b>Telegram Business API</b> standartlari asosida ishlaydi:\n\n"
            "• <b>Shaxsiy foydalanish:</b> O'chirilgan xabarlarning barcha nusxalari faqat sizning shaxsiy botingizga yetkaziladi.\n"
            "• <b>Vaqtinchalik kesh:</b> Ma'lumotlar xotirada ko'pi bilan 3 kun saqlanadi va avtomatik o'chiriladi.\n"
            "• <b>To'liq nazorat:</b> Siz istalgan vaqtda bot qaysi chatlarda ishlashini sozlashingiz yoki butunlay uzib qo'yishingiz mumkin.\n\n"
            "🌐 Maxfiylik siyosatining to'liq veb-sahifasi bilan tanishing:"
        ),


        # Referral
        "referral_title": "🎁 <b>Referal tizimi</b>\n\n",
        "referral_body": (
            "Do'stlaringizni botga taklif qiling va botni o'z profiliga ulagan har bir do'stingiz uchun "
            "<b>+1 kun bepul obuna</b> oling!\n\n"
            "📊 <b>Sizning statistikangiz:</b>\n"
            "• Taklif qilingan do'stlar: <b>{invited} / {max_limit}</b>\n"
            "• Botni profiliga ulaganlar: <b>{connected} ta</b>\n"
            "• Olingan bonus kunlar: <b>+{reward_days} kun</b>\n"
            "• Taklif uchun qolgan o'rinlar: <b>{remaining} ta</b>\n\n"
            "🔗 <b>Sizning shaxsiy havolangiz:</b>\n<code>{ref_link}</code>\n\n"
            "⚠️ <i>Bonus do'stingiz botni Telegram Business orqali o'z profiliga ulashi bilanoq avtomatik qo'shiladi!</i>"
        ),
        "referral_disabled": "⚠️ <b>Referal tizimi vaqtincha administrator tomonidan to'xtatilgan.</b>",
        "referral_reward_notify": (
            "🎉 <b>Ajoyib xushxabar!</b>\n\n"
            "Siz taklif qilgan do'stingiz botni o'z profiliga muvaffaqiyatli uladi!\n"
            "Sizga taqdim etildi: <b>+1 kun bepul obuna</b> 🎁\n"
            "Yangi amal qilish muddati: <code>{expires_at}</code>."
        ),
        "btn_share_ref": "📲 Do'stlarga ulashish",
        "share_text": "Salom! Telegram Business uchun bu botni sinab ko'r — o'chirilgan xabarlar va 1 martalik rasm/videolarni saqlab beradi:",

        # Tilni o'zgartirish
        "choose_lang": "🌐 <b>Tilni tanlang / Выберите язык:</b>",
        "lang_selected": "✅ <b>Til muvaffaqiyatli O'zbek tiliga o'zgartirildi!</b>",

        # Ulanish holati
        "conn_trial": (
            "\n\n🎁 <b>Sizga 7 KUNLIK BEPUL SINOV (Free Trial) faollashtirildi!</b>\n"
            "1 hafta davomida bot barcha o'chirilgan xabarlar va 1 martalik medialarni to'liq tutib beradi."
        ),
        "conn_success": (
            "✅ <b>Bot profilingizga muvaffaqiyatli ulandi!</b>\n\n"
            "👤 Profil: <b>{user_name}</b>"
            "{trial_text}\n\n"
            "📖 <b>Qanday ishlatiladi?</b>\n"
            "➖ <b>O'chirilgan xabarlar:</b> Suhbatdoshingiz biror xabarni o'chirsa, bot darhol sizga o'sha xabarning nusxasini (matn, rasm, video, audio) yetkazadi.\n"
            "➖ <b>O'zgartirilgan xabarlar:</b> Xabar tahrirlansa, eski va yangi matni sizga yuboriladi.\n"
            "➖ <b>1 martalik (taymerli) medialar:</b> Suhbatdoshingiz yuborgan 1 martalik rasm yoki videoni saqlash uchun — <b>uni ochishdan oldin</b> chatda o'sha xabarga istalgan so'z yoki belgi bilan <b>javob (Reply)</b> qaytaring (masalan nuqta <code>.</code> qo'ying). Bot uni darhol saqlab, sizga jo'natadi!\n\n"
            "❗️ <i>Eslatma: Bot ulanishdan keyin kelgan yangi xabarlarni kuzatadi.</i>"
        ),
        "conn_disabled": (
            "⚠️ <b>Bot profildan uzildi!</b>\n\n"
            "👤 Profil: {user_name}\n"
            "Kuzatuv to'xtatildi."
        ),

        # Tahrirlangan xabar
        "msg_edited": (
            "✏️ <b>Xabar o'zgartirildi!</b>\n\n"
            "👤 <b>Kimdan:</b> {who} ({sender_name})\n"
            "👥 <b>Chat:</b> {chat_title}\n\n"
            "❌ <b>Eski xabar:</b>\n<blockquote>{old_text}</blockquote>\n"
            "✅ <b>Yangi xabar:</b>\n<blockquote>{new_text}</blockquote>"
        ),

        # 1 martalik media
        "msg_view_once": (
            "👁 <b>1 martalik (taymerli) media saqlandi!</b>\n\n"
            "👤 <b>Kimdan:</b> {sender_name}\n"
            "💬 <b>Chat:</b> {chat_title}\n"
            "🕒 <b>Vaqti:</b> {time_str}\n"
        ),
        "msg_view_once_footer": "\n🎯 <i>Siz xabarga javob (reply) berganingiz uchun bot uni sizga saqlab berdi!</i>",

        # O'chirilgan xabar
        "msg_deleted_title": "🗑 <b>O'chirilgan xabar</b>\n\n",
        "msg_deleted_body": (
            "👤 <b>Kimdan:</b> {who} ({sender_name})\n"
            "👥 <b>Chat:</b> {chat_title}\n"
            "🕒 <b>Yuborilgan:</b> {sent_time}\n"
            "🗑 <b>O'chirilgan:</b> {delete_time}\n\n"
        ),
        "promo_footer": (
            "\n\n➖➖➖➖➖➖➖➖➖➖\n"
            "🕵️‍♂️ <b>@seenspybot orqali saqlab olindi</b>\n"
            "👉 <i>Profilingizdagi o'chirilgan xabarlarni ko'ring!</i>"
        ),


        # Teaserlar
        "teaser_deleted_title": "🔒 <b>Sizda yangi o'chirilgan xabar bor!</b>\n\n",
        "teaser_deleted_body": (
            "Chatlaringizda kimdir xabarni o'chirib yubordi.\n"
            "U arxivda xavfsiz saqlanmoqda.\n"
            "📦 Hozirgacha yig'ilgan ko'rilmagan xabarlar soni: <b>{total_missed} ta</b>\n\n"
            "Ularni ko'rish uchun obunani faollashtiring!\n"
            "👉 Quyidagi tugmani bosing yoki /buy buyrug'ini yuboring."
        ),
        "teaser_view_once": (
            "🔒 <b>Sizda yangi 1 martalik media bor!</b>\n\n"
            "Chatlaringizda yangi 1 martalik rasm/video tutib olindi va xavfsiz arxivlandi.\n"
            "📦 Hozirgacha yig'ilgan ko'rilmagan xabarlar soni: <b>{total_missed} ta</b>\n\n"
            "Uni ko'rish va saqlash uchun obunani faollashtiring!\n"
            "👉 Quyidagi tugmani bosing yoki /buy buyrug'ini yuboring."
        ),
        "btn_unlock": "🔓 Xabarlarni ko'rish ({total_missed} ta)",

        # Tariflar va to'lovlar
        "plans_title": (
            "⭐️ <b>Obuna Tariflari</b>\n\n"
            "O'chirilgan xabarlar va 1 martalik medialarni to'liq ko'rish uchun mos tarifni tanlang:\n\n"
            "• <b>1 Hafta</b> — 5 Stars\n"
            "• <b>1 Oy</b> — 15 Stars <i>(25% chegirma)</i>\n"
            "• <b>1 Yil</b> — 180 Stars <i>(Eng manfaatli)</i>\n\n"
            "To'lov xavfsiz tarzda rasmiy <b>Telegram Stars</b> ⭐ orqali amalga oshiriladi."
        ),
        "plan_week_name": "1 Hafta (7 kun)",
        "plan_week_desc": "O'chirilgan va 1 martalik xabarlarni 7 kun davomida tutib olish xizmati",
        "plan_month_name": "1 Oy (30 kun)",
        "plan_month_desc": "O'chirilgan va 1 martalik xabarlarni 30 kun davomida tutib olish xizmati (Tejamkor)",
        "plan_year_name": "1 Yil (365 kun)",
        "plan_year_desc": "O'chirilgan va 1 martalik xabarlarni 365 kun davomida tutib olish xizmati (Eng manfaatli)",
        "invoice_title": "Obuna: {plan_name}",
        "payment_success": (
            "🎉 <b>To'lov muvaffaqiyatli qabul qilindi!</b>\n\n"
            "⭐️ Tarif: <b>{plan_name}</b>\n"
            "⏳ Amal qilish muddati: <code>{expires_at}</code> gacha\n\n"
            "Obuna uchun rahmat! Barcha xizmatlar to'liq faol."
        ),
        "payment_replay_header": (
            "📦 <b>Arxivdagi xabarlar:</b>\n"
            "Sizda to'lov qilinmagan davrda yig'ilgan <b>{count} ta xabar</b> mavjud edi. "
            "Ular hozir sizga yuborilmoqda:\n"
        ),

        # Scheduler
        "scheduler_expired": (
            "⏳ <b>Obunangiz muddati tugadi!</b>\n\n"
            "Sizning obuna muddatingiz yakunlandi (Tugash vaqti: <code>{exp_date}</code>).\n\n"
            "Endi chatlaringizdagi o'chirilgan xabarlar va 1 martalik medialarni to'liq ko'rish uchun obunani yangilashingiz lozim.\n\n"
            "📦 <i>Xavotir olmang, yangi kelgan barcha o'chirilgan xabarlar xavfsiz arxivlanib turadi va to'lov qilishingiz bilan barchasi botingizga to'liq yetkaziladi!</i>\n\n"
            "👉 Yangilash uchun quyidagi tugmani bosing yoki /buy buyrug'ini yuboring."
        ),
        "btn_renew_sub": "⭐ Obunani yangilash",
        "scheduler_cutoff": (
            "⚠️ <b>Obunangiz tugaganiga 30 kundan oshdi!</b>\n\n"
            "Siz 1 oy davomida obunani yangilamaganingiz sababli, yangi o'chirilgan xabarlarni zaxira qilish to'xtatildi.\n\n"
            "Xizmatni qayta tiklash va arxivni saqlashni davom ettirish uchun quyidagi tugma orqali obuna bo'ling.\n\n"
            "👉 Qayta yoqish uchun: /buy"
        ),
    }
}


def get_text(key: str, lang: Optional[str] = "ru", **kwargs: Any) -> str:
    """Belgilangan tildagi matnni olish (Birlamchi til: ru)."""
    current_lang = lang if lang in MESSAGES else DEFAULT_LANGUAGE
    template = MESSAGES[current_lang].get(key)
    if not template:
        # Fallback to Russian
        template = MESSAGES[DEFAULT_LANGUAGE].get(key, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template


def get_main_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Asosiy menyu klaviaturasi (Tanlangan tilda)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_connect", lang),
                    url="tg://settings/edit"
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("btn_plans", lang),
                    callback_data="show_plans"
                ),
                InlineKeyboardButton(
                    text=get_text("btn_referral", lang),
                    callback_data="show_referral"
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("btn_language", lang),
                    callback_data="choose_lang"
                ),
                InlineKeyboardButton(
                    text=get_text("btn_privacy", lang),
                    url=PRIVACY_POLICY_URL
                )
            ]
        ]
    )




def get_language_keyboard() -> InlineKeyboardMarkup:
    """Til tanlash klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang:ru"),
                InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="set_lang:uz")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад / Orqaga", callback_data="back_to_menu")
            ]
        ]
    )


def get_plans_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Tariflar tanlash klaviaturasi (Tanlangan tilda)."""
    w_stars = 5
    m_stars = 15
    y_stars = 180

    if lang == "uz":
        w_text = f"⭐ 1 Hafta — {w_stars} Stars"
        m_text = f"⭐ 1 Oy — {m_stars} Stars (25% chegirma)"
        y_text = f"⭐ 1 Yil — {y_stars} Stars (Eng manfaatli)"
    else:
        w_text = f"⭐ 1 Неделя — {w_stars} Stars"
        m_text = f"⭐ 1 Месяц — {m_stars} Stars (-25%)"
        y_text = f"⭐ 1 Год — {y_stars} Stars (Выгодно)"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=w_text, callback_data="buy:week")],
            [InlineKeyboardButton(text=m_text, callback_data="buy:month")],
            [InlineKeyboardButton(text=y_text, callback_data="buy:year")],
            [InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="back_to_menu")]
        ]
    )

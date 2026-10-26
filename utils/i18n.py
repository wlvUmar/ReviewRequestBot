# utils/i18n.py

MESSAGES = {
    "ru": {
        "choose_language": "🌐 Выберите язык / Tilni tanlang",
        "share_phone": "📱 Поделиться номером",
        "phone_prompt": "📲 Чтобы начать, отправьте номер телефона — это нужно, чтобы мы могли связаться с вами по заявке.",
        "phone_invalid": "⚠️ Введите номер телефона в формате +998901234567 или нажмите кнопку «📱 Поделиться номером».",
        "phone_not_own": "❗ Пожалуйста, используйте свой личный номер телефона.",
        "welcome": "Отлично, <b>{first_name}</b> 🙂\n\n<b>Шаг 1 из 3 · Фото</b> 📷\nОтправьте фото товара — до {max_photos} штук. Лучше с разных сторон, чтобы были видны дефекты.\n\nКоманды: /help",
        "new_request_prompt": "<b>Шаг 1 из 3 · Фото</b> 📷\nОтправьте фото товара — до {max_photos} штук. Лучше с разных сторон, чтобы были видны дефекты.",
        "send_photo_first": "📷 Сначала отправьте фото",
        "wrong_state_photo": "📷 Отправьте фото товара, чтобы создать заявку.\nПомощь: /help",
        "wrong_state_preview": "👆 Нажмите «{submit}» под превью, «✏️ Изменить» или /cancel.",
        "language_set": "🌐 Язык установлен: Русский",
        "submit_button": "📤 Отправить",

        "photo_progress_full": "📸 <b>Фото принято:</b> {count}/{max}\n\n➕ Можно добавить ещё фото.\n\n<b>Шаг 2 из 3 · Описание</b> ✍️\nНапишите, что это за товар, в каком он состоянии и есть ли дефекты.",
        "photo_progress_done": "📸 <b>Фото принято:</b> {count}/{max}\n\n<b>Шаг 2 из 3 · Описание</b> ✍️\nНапишите, что это за товар, в каком он состоянии и есть ли дефекты.",
        "photo_progress_caption": "\n\n✅ Подпись к фото принята — можно сразу нажать «Далее».",
        "photo_progress_ask_price": "📸 <b>Фото принято:</b> {count}/{max}\n\n➕ Можно отправить ещё фото или укажите желаемую цену:",

        "price_prompt": "<b>Шаг 3 из 3 · Цена</b> 💰\nУкажите желаемую цену, например: 1 500 000 или 120 usd.\nЕсли не знаете — нажмите кнопку ниже.",
        "price_invalid": "⚠️ Не вижу цифр. Введите сумму цифрами, например: 1 500 000 или 120 usd — или нажмите «Не знаю».",
        "price_saved": "✅ Цена принята.",
        "price_not_set": "не указана",

        "description_prompt": "📝 Опишите товар: что это, состояние, дефекты.",
        "desired_price_label": "💰 Цена",

        "photo_limit_reached": "🚫 Максимум {max} фото за один запрос.\n\nПереходим дальше — опишите товар текстом.",

        "use_start_first": "🔄 Пожалуйста, используйте /start.",
        "description_too_long": "⚠️ Описание слишком длинное. Пожалуйста, сократите до 2000 символов.",
        "send_description_first": "📄 Сначала отправьте описание товара текстом.",
        "description_progress": "📝 <b>Описание принято</b> ({chars}/2000)\n\nМожно дополнить текстом или нажмите «{next}».",
        "next_button": "Далее ➡️",

        "btn_cancel": "❌ Отмена",
        "btn_price_skip": "🤝 Не знаю / договорная",
        "btn_edit": "✏️ Изменить",
        "btn_new_request": "➕ Новая заявка",
        "btn_status": "📋 Статус заявки",

        "preview_title": "<b>Проверьте заявку</b>",
        "preview_note": "Если всё верно — нажмите «{submit}».",
        "preview_more_photos": "(➕{more} фото, показано первое)",
        "edit_prompt": "✏️ Хорошо, опишите товар заново: что это, состояние, дефекты.",
        "cancelled": "🗑 Заявка отменена. Когда будете готовы — отправьте фото товара.",

        "image_download_failed": "⚠️ Не удалось загрузить изображения. Попробуйте ещё раз.",
        "request_submitted": "✅ <b>Заявка №{request_id} принята!</b>\n\nМы посмотрим фото и пришлём оценку прямо в этот чат. Возможно, мы позвоним вам.",
        "request_submitted_phone": "✅ <b>Заявка №{request_id} принята!</b>\n\nМы посмотрим фото и пришлём оценку прямо в этот чат. Возможно, мы позвоним вам по номеру {phone}.",
        "api_upload_failed": "⏳ Не удалось отправить заявку. Ваши фото сохранены — нажмите «Отправить» ещё раз через 1–2 минуты.",
        "save_error": "❌ Произошла ошибка при сохранении данных. Пожалуйста, попробуйте позже.",
        "submitting_request": "⏳ Отправляем заявку… Это может занять до минуты.",

        "help_text": "<b>Как это работает</b>\n1. Отправьте фото товара\n2. Опишите его\n3. Назовите желаемую цену\n\nМы оценим и ответим прямо здесь.\n\n<b>Команды</b>\n/start — новая заявка\n/status — статус последней заявки\n/lang — сменить язык\n/cancel — отменить текущую заявку\n/help — эта справка",
        "status_none": "У вас пока нет заявок. Отправьте фото товара, чтобы создать первую.",
        "status_pending": "⏳ Заявка №{request_id}: в обработке. Как только оценка будет готова, мы пришлём её сюда.",
        "status_approved": "✅ Заявка №{request_id}: оценка готова\n💰 {price}",
        "status_rejected": "📦 Заявка №{request_id}: сейчас не можем дать точную оценку.",
        "status_error": "⚠️ Не удалось получить статус. Попробуйте чуть позже.",
        "lang_pick": "🌐 Выберите язык / Tilni tanlang",

        "reject_not_in_category": "ℹ️ Спасибо за обращение. К сожалению, мы не скупаем этот вид товара. Мы принимаем бытовую технику и мебель.",
        "reject_low_profit": "ℹ️ Спасибо за обращение. К сожалению, мы не сможем предложить подходящую цену по этому товару.",
        "reject": "📦 Спасибо! Мы получили фотографии. Сейчас не можем дать точную оценку.",
        "approved_price": "💰 Оценка: {price}",
        "approved_contact": "📞 Контакт: {phone}",
        "approved_notes": "📝 Комментарий: {notes}",
        "reject_notes": "📝 Комментарий: {notes}",
    },

    "uz": {
        "choose_language": "🌐 Tilni tanlang / Выберите язык",
        "share_phone": "📱 Telefon raqamini yuboring",
        "phone_prompt": "📲 Boshlash uchun telefon raqamingizni yuboring — bu arizangiz bo'yicha siz bilan bog'lanish uchun kerak.",
        "phone_invalid": "⚠️ Telefon raqamingizni +998901234567 formatida kiriting yoki «📱 Telefon raqamini yuboring» tugmasini bosing.",
        "phone_not_own": "❗ Iltimos, o'z telefon raqamingizni yuboring.",

        "welcome": "Ajoyib, <b>{first_name}</b> 🙂\n\n<b>1/3-qadam · Rasm</b> 📷\nMahsulot rasmini yuboring — {max_photos} tagacha. Kamchiliklar ko'rinishi uchun turli tomondan olgan ma'qul.\n\nBuyruqlar: /help",
        "new_request_prompt": "<b>1/3-qadam · Rasm</b> 📷\nMahsulot rasmini yuboring — {max_photos} tagacha. Kamchiliklar ko'rinishi uchun turli tomondan olgan ma'qul.",
        "send_photo_first": "📷 Avval surat yuboring",
        "wrong_state_photo": "📷 Ariza yaratish uchun mahsulot rasmini yuboring.\nYordam: /help",
        "wrong_state_preview": "👆 Prevyu ostidagi «{submit}» yoki «✏️ O'zgartirish» tugmasini bosing, yoki /cancel.",
        "language_set": "🌐 Til belgilandi: O'zbekcha",
        "submit_button": "📤 Yuborish",

        "photo_progress_full": "📸 <b>Rasm qabul qilindi:</b> {count}/{max}\n\n➕ Yana rasm qo'shishingiz mumkin.\n\n<b>2/3-qadam · Tavsif</b> ✍️\nBu qanday mahsulot, holati qanday va kamchiliklari bormi — yozing.",
        "photo_progress_done": "📸 <b>Rasm qabul qilindi:</b> {count}/{max}\n\n<b>2/3-qadam · Tavsif</b> ✍️\nBu qanday mahsulot, holati qanday va kamchiliklari bormi — yozing.",
        "photo_progress_caption": "\n\n✅ Rasm izohi qabul qilindi — darhol «Keyingisi» tugmasini bosishingiz mumkin.",
        "photo_progress_ask_price": "📸 <b>Rasm qabul qilindi:</b> {count}/{max}\n\n➕ Yana rasm yuborishingiz yoki xohlagan sotuv narxingizni kiriting:",

        "price_prompt": "<b>3/3-qadam · Narx</b> 💰\nXohlagan narxingizni kiriting, masalan: 1 500 000 yoki 120 usd.\nBilmasangiz — pastdagi tugmani bosing.",
        "price_invalid": "⚠️ Raqam topilmadi. Summani raqamda kiriting, masalan: 1 500 000 yoki 120 usd — yoki «Bilmayman» tugmasini bosing.",
        "price_saved": "✅ Narx qabul qilindi.",
        "price_not_set": "ko'rsatilmagan",

        "description_prompt": "📝 Mahsulotni tasvirlang: nima ekanligini, holatini va kamchiliklarini.",
        "desired_price_label": "💰 Narx",
        "description_progress": "📝 <b>Tavsif qabul qilindi</b> ({chars}/2000)\n\nMatn bilan to'ldirishingiz yoki «{next}» tugmasini bosishingiz mumkin.",
        "next_button": "Keyingisi ➡️",
        "photo_limit_reached": "🚫 Maksimum {max} ta rasm qabul qilinadi.\n\nDavom etamiz — mahsulotni matn bilan tasvirlang.",

        "btn_cancel": "❌ Bekor qilish",
        "btn_price_skip": "🤝 Bilmayman / kelishiladi",
        "btn_edit": "✏️ O'zgartirish",
        "btn_new_request": "➕ Yangi ariza",
        "btn_status": "📋 Ariza holati",

        "use_start_first": "🔄 /start buyrug'ini yuborib, jarayonni qayta boshlang.",
        "description_too_long": "⚠️ Matn juda uzun. Iltimos, 2000 belgigacha qisqartiring.",
        "send_description_first": "📄 Avval mahsulot tavsifini matn ko'rinishida yuboring.",

        "preview_title": "<b>Arizani tekshiring</b>",
        "preview_note": "Hammasi to'g'ri bo'lsa — «{submit}» tugmasini bosing.",
        "preview_more_photos": "(➕{more} rasm, birinchi ko'rsatilgan)",
        "edit_prompt": "✏️ Yaxshi, mahsulotni qaytadan tasvirlang: nima ekanligini, holatini va kamchiliklarini.",
        "cancelled": "🗑 Ariza bekor qilindi. Tayyor bo'lganingizda mahsulot rasmini yuboring.",

        "image_download_failed": "⚠️ Rasmlarni yuklab olishning imkoni bo'lmadi. Yana urinib ko'ring.",
        "request_submitted": "✅ <b>№{request_id} ariza qabul qilindi!</b>\n\nRasmlarni ko'rib chiqib, bahoni shu chatning o'ziga yuboramiz. Sizga qo'ng'iroq qilishimiz mumkin.",
        "request_submitted_phone": "✅ <b>№{request_id} ariza qabul qilindi!</b>\n\nRasmlarni ko'rib chiqib, bahoni shu chatning o'ziga yuboramiz. Sizga {phone} raqami orqali qo'ng'iroq qilishimiz mumkin.",
        "api_upload_failed": "⏳ Arizani yuborib bo'lmadi. Rasmlaringiz saqlangan — 1–2 daqiqadan so'ng «Yuborish» tugmasini yana bosing.",
        "save_error": "❌ Ma'lumotlarni saqlashda xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring.",
        "submitting_request": "⏳ Ariza yuborilmoqda… Bu bir daqiqagacha vaqt olishi mumkin.",

        "help_text": "<b>Bu qanday ishlaydi</b>\n1. Mahsulot rasmini yuboring\n2. Uni tasvirlang\n3. Xohlagan narxni ayting\n\nBiz baholab, javobni shu yerning o'ziga yuboramiz.\n\n<b>Buyruqlar</b>\n/start — yangi ariza\n/status — oxirgi ariza holati\n/lang — tilni o'zgartirish\n/cancel — joriy arizani bekor qilish\n/help — shu ma'lumot",
        "status_none": "Sizda hali ariza yo'q. Birinchisini yaratish uchun mahsulot rasmini yuboring.",
        "status_pending": "⏳ №{request_id} ariza: ko'rib chiqilmoqda. Baho tayyor bo'lishi bilan bu yerga yuboramiz.",
        "status_approved": "✅ №{request_id} ariza: baho tayyor\n💰 {price}",
        "status_rejected": "📦 №{request_id} ariza: hozir aniq baho bera olmaymiz.",
        "status_error": "⚠️ Holatni olib bo'lmadi. Birozdan so'ng qayta urinib ko'ring.",
        "lang_pick": "🌐 Tilni tanlang / Выберите язык",

        "reject_not_in_category": "ℹ️ Murojaat uchun rahmat. Afsuski, biz bu turdagi mahsulotni sotib olmaymiz. Biz maishiy texnika va mebel qabul qilamiz.",
        "reject_low_profit": "ℹ️ Murojaat uchun rahmat. Afsuski, bu mahsulot uchun mos narx taklif eta olmaymiz.",
        "reject": "📦 Rahmat! Rasmlarni oldik. Hozir aniq baho bera olmaymiz.",
        "approved_price": "💰 Baho: {price}",
        "approved_contact": "📞 Aloqa: {phone}",
        "approved_notes": "📝 Izoh: {notes}",
        "reject_notes": "📝 Izoh: {notes}",
    },
}
DEFAULT_LANG = "ru"


def t(lang: str, key: str, **kwargs) -> str:
    if not lang:
        lang = DEFAULT_LANG
    data = MESSAGES.get(lang, MESSAGES[DEFAULT_LANG])
    template = data.get(key) or MESSAGES[DEFAULT_LANG].get(key, "")
    try:
        return template.format(**kwargs)
    except Exception:
        return template

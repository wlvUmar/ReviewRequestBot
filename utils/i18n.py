# utils/i18n.py

MESSAGES = {
    "ru": {
        "choose_language": "🌐 Выберите язык / Tilni tanlang",
        "share_phone": "📱 Поделиться номером",
        "phone_prompt": "📲 Чтобы начать, отправьте номер телефона — это нужно для обработки заявки.",
        "phone_invalid": "⚠️ Введите номер телефона в формате +998901234567 или нажмите кнопку «📱 Поделиться номером».",
        "phone_not_own": "❗ Пожалуйста, используйте свой личный номер телефона.",
        "welcome": "Отлично, <b>{first_name}</b> 🙂\n\n📷 Отправьте фото товара.\nМожно до {max_photos} фото за один запрос.\nПосле этого мы отправим оценку.",
        "send_photo_first": "📷 Сначала отправьте фото",
        "language_set": "🌐 Язык установлен: Русский",
        "submit_button": "📤 Отправить",

        "photo_progress_full": "📸 <b>Фото принято:</b> {count}/{max}\n\n➕ Можно отправить ещё фото или опишите товар:\n— что это\n— состояние\n— дефекты",

        "photo_progress_done": "📸 <b>Фото принято:</b> {count}/{max}\n\nОпишите товар:\n— что это\n— состояние\n— дефекты",

        "photo_progress_ask_price": "📸 <b>Фото принято:</b> {count}/{max}\n\n➕ Можно отправить ещё фото или укажите желаемую цену:",

        "price_prompt": "💰 Укажите желаемую цену (например: 150000 или 12 usd):",
        "price_invalid": "⚠️ Неверный формат. Введите сумму цифрами, например: 1 500 000 или 120 usd",
        "price_saved": "✅ Цена принята.",

        "description_prompt": "📝 Опишите товар: что это, состояние, дефекты.",
        "desired_price_label": "💰 цена",

        "photo_limit_reached": "🚫 Максимум {max} фото за один запрос.\n\n💰 Теперь укажите желаемую цену:",

        "use_start_first": "🔄 Пожалуйста, используйте /start.",
        "description_too_long": "⚠️ Описание слишком длинное. Пожалуйста, сократите до 2000 символов.",
        "send_description_first": "📄 Сначала отправьте описание товара текстом.",
        "description_progress": "📝 <b>Описание принято</b> ({chars}/2000)\n\nМожно дополнить или нажмите «{next}» чтобы продолжить.",
        "next_button": "Далее ➡️",

        "preview_note": "✏️ Можно дополнить описание. Нажмите \"{submit}\" или отправьте текст — превью обновится.",
        "preview_more_photos": "(➕{more} фото, показано первое)",

        "image_download_failed": "⚠️ Не удалось загрузить изображения. Попробуйте ещё раз.",
        "request_submitted": "📨 Изображения отправлены. Скоро отправим оценку.",
        "api_upload_failed": "⏳ Не удалось отправить изображение. Попробуйте через 1–2 минуты.",
        "save_error": "❌ Произошла ошибка при сохранении данных. Пожалуйста, попробуйте позже.",
        "submitting_request": "⏳ Отправляем заявку...",
        "reject_not_in_category": "ℹ️ Спасибо за обращение. К сожалению, мы не скупаем этот вид товара. Мы принимаем бытовую технику и мебель.",
        "reject_low_profit": "ℹ️ Спасибо за обращение. К сожалению, мы не сможем предложить подходящую цену по этому товару.",
        "reject": "📦 Спасибо! Мы получили фотографии. Сейчас не можем дать точную оценку.",
    },

    "uz": {
        "choose_language": "🌐 Tilni tanlang / Выберите язык",
        "share_phone": "📱 Telefon raqamini yuboring",
        "phone_prompt": "📲 Boshlash uchun telefon raqamingizni yuboring — bu bizga murojaat qilish uchun kerak.",
        "phone_invalid": "⚠️ Telefon raqamingizni +998901234567 formatida kiriting yoki «📱 Telefon raqamini yuboring» tugmasini bosing.",
        "phone_not_own": "❗ Iltimos, o'z telefon raqamingizni yuboring.",

        "welcome": "Ajoyib, <b>{first_name}</b> 🙂\n\n📷 Mahsulot fotosuratini yuboring.\nBitta so'rov uchun {max_photos} tagacha rasm yuborishingiz mumkin.\nShundan so'ng biz bahoni yuboramiz.",

        "send_photo_first": "📷 Avval surat yuboring",
        "language_set": "🌐 Til belgilandi: O'zbekcha",
        "submit_button": "📤 Yuborish",

        "photo_progress_full": "📸 <b>Rasm qabul qilindi:</b> {count}/{max}\n\n➕ Yana rasm yuborishingiz yoki mahsulotni tasvirlashingiz mumkin:\n— bu nima\n— holati\n— kamchiliklar",

        "photo_progress_done": "📸 <b>Rasm qabul qilindi:</b> {count}/{max}\n\nMahsulotni tasvirlang:\n— bu nima\n— holati\n— kamchiliklar",

        "photo_progress_ask_price": "📸 <b>Rasm qabul qilindi:</b> {count}/{max}\n\n➕ Yana rasm yuborishingiz yoki xohlagan sotuv narxingizni kiriting:",

        "price_prompt": "💰 Xohlagan sotuv narxingizni kiriting (masalan: 1500000 yoki 12 usd):",
        "price_invalid": "⚠️ Noto'g'ri format. Summani raqamda kiriting, masalan: 1 500 000 yoki 120 usd",
        "price_saved": "✅ Narx qabul qilindi.",

        "description_prompt": "📝 Mahsulotni tasvirlang: nima ekanligini, holatini va kamchiliklarini.",
        "desired_price_label": "💰 Narx",
        "description_progress": "📝 <b>Tavsif qabul qilindi</b> ({chars}/2000)\n\nTo'ldirishingiz yoki «{next}» tugmasini bosing.",
        "next_button": "Keyingisi ➡️",
        "photo_limit_reached": "🚫 Maksimum {max} ta rasm qabul qilinadi.\n\n💰 Endi xohlagan sotuv narxingizni kiriting:",

        "use_start_first": "🔄 /start buyrug'ini yuborib, jarayonni qayta boshlang.",
        "description_too_long": "⚠️ Matn juda uzun. Iltimos, 2000 belgigacha qisqartiring.",
        "send_description_first": "📄 Avval mahsulot tavsifini matn ko'rinishida yuboring.",

        "preview_note": "✏️ Tavsifni to'ldirishingiz mumkin. \"{submit}\" tugmasini bosing yoki qo'shimcha matn yuboring — prevyu yangilanadi.",
        "preview_more_photos": "(➕{more} rasm, birinchi ko'rsatilgan)",

        "image_download_failed": "⚠️ Rasmlarni yuklab olishning imkoni bo'lmadi. Yana urinib ko'ring.",
        "request_submitted": "📨 Rasmlar yuborildi. Tez orada baho yuboramiz.",
        "api_upload_failed": "⏳ Rasmni yuborib bo'lmadi. 1–2 daqiqadan so'ng qayta urinib ko'ring.",
        "save_error": "❌ Ma'lumotlarni saqlashda xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring.",
        "submitting_request": "⏳ So'rov yuborilmoqda...",

        "reject_not_in_category": "ℹ️ Murojaat uchun rahmat. Afsuski, biz bu turdagi mahsulotni sotib olmaymiz. Biz maishiy texnika va mebel qabul qilamiz.",
        "reject_low_profit": "ℹ️ Murojaat uchun rahmat. Afsuski, bu mahsulot uchun mos narx taklif eta olmaymiz.",
        "reject": "📦 Rahmat! Rasmlarni oldik. Hozir aniq baho bera olmaymiz.",
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
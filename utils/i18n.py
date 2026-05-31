# Simple i18n mapper for RU and UZ languages.
# Keys are looked up by language code ('ru' or 'uz').

MESSAGES = {
    "ru": {
        "choose_language": "Выберите язык / Tilni tanlang",
        "share_phone": "📱 Поделиться номером",
        "phone_prompt": "Для начала поделитесь вашим номером телефона — это нужно, чтобы мы могли связаться с вами по заявке.",
        "phone_not_own": "⚠️ Пожалуйста, поделитесь своим собственным номером.",
        "welcome": "✅ Отлично, <b>{first_name}</b>!\n\nОтправьте фото товара.\nМожно до {max_photos} фото за один запрос.\nПосле этого мы пришлём оценку сюда.",
        "send_photo_first": "Сначала отправьте фото.",
        "language_set": "Язык установлен: Русский",
        "submit_button": "Отправить",
        "photo_progress": "📸 <b>Фото принято:</b> {count}/{max}\n\n📝 <b>Теперь отправьте информацию о товаре:</b>\n— что это за вещь\n— состояние\n— желаемая цена продажи",
        "photo_received_ask_price": "📸 <b>Фото принято:</b> {count}/{max}\n\n💰 Укажите желаемую цену продажи:",
        "price_prompt": "💰 Укажите желаемую цену продажи (только цифры, например: 150000):",
        "price_invalid": "⚠️ Неверный формат. Введите сумму цифрами, например: 150000",
        "price_saved": "✅ Цена принята.",
        "description_prompt": "📝 Теперь опишите товар: что это, состояние, любые детали.",
        "desired_price_label": "Желаемая цена",
        "photo_limit_reached": "⚠️ Максимум {max} фото — только первые {max} будут отправлены на оценку.\n\n📝 Теперь отправьте краткую информацию о товаре.",
        "use_start_first": "Неверный порядок действий. Пожалуйста, используйте /start.",
        "description_too_long": "Описание слишком длинное. Пожалуйста, сократите до 2000 символов.",
        "send_description_first": "Сначала отправьте описание товара текстом.",
        "preview_note": "Вы можете дополнить описание. Нажмите \"{submit}\" чтобы отправить заявку, или просто пришлите ещё текст — превью обновится.",
        "preview_more_photos": "(+{more} фото, показано первое)",
    },
    "uz": {
        "choose_language": "Tilni tanlang / Выберите язык",
        "share_phone": "📱 Telefon raqamini yuboring",
        "phone_prompt": "Boshlash uchun telefon raqamingizni yuboring — bu bizga murojaat qilish uchun kerak.",
        "phone_not_own": "⚠️ Iltimos, o'z telefon raqamingizni yuboring.",
        "welcome": "✅ Ajoyib, <b>{first_name}</b>!\n\nMahsulot fotosuratini yuboring.\nBitta so'rov uchun {max_photos} tagacha rasm yuborishingiz mumkin.\nShundan so'ng biz bahoni yuboramiz.",
        "send_photo_first": "Avval surat yuboring.",
        "language_set": "Til belgilandi: O'zbekcha",
        "submit_button": "Yuborish",
        "photo_progress": "📸 <b>Rasm qabul qilindi:</b> {count}/{max}\n\n📝 <b>Endi mahsulot haqida ma'lumot yuboring:</b>\n— bu nima mahsulot\n— holati\n— xohlagan sotuv narxi",
        "photo_received_ask_price": "📸 <b>Rasm qabul qilindi:</b> {count}/{max}\n\n💰 Xohlagan sotuv narxingizni kiriting:",
        "price_prompt": "💰 Xohlagan sotuv narxingizni kiriting (faqat raqamlar, masalan: 150000):",
        "price_invalid": "⚠️ Noto'g'ri format. Summani raqamda kiriting, masalan: 150000",
        "price_saved": "✅ Narx qabul qilindi.",
        "description_prompt": "📝 Endi mahsulotni tasvirlang: nima ekanligini, holatini va boshqa ma'lumotlarni.",
        "desired_price_label": "Xohlagan narx",
        "photo_limit_reached": "⚠️ Maksimum {max} ta rasm qabul qilinadi. Endi mahsulot haqida qisqa ma'lumot yuboring.",
        "use_start_first": "/start buyrug'ini yuborib, jarayonni qayta boshlang.",
        "description_too_long": "Matn juda uzun. Iltimos, 2000 belgigacha qisqartiring.",
        "send_description_first": "Avval mahsulot tavsifini matn ko'rinishida yuboring.",
        "preview_note": "Tavsifni to'ldirishingiz mumkin. Yuborish uchun \"{submit}\" tugmasini bosing yoki qo'shimcha matn yuboring — prevyu yangilanadi.",
        "preview_more_photos": "(+{more} rasm, birinchi ko'rsatilgan)",
    }
}

DEFAULT_LANG = "ru"


def t(lang: str, key: str, **kwargs) -> str:
    """Translate key for given lang, format with kwargs. Falls back to default lang."""
    if not lang:
        lang = DEFAULT_LANG
    data = MESSAGES.get(lang, MESSAGES[DEFAULT_LANG])
    template = data.get(key) or MESSAGES[DEFAULT_LANG].get(key, "")
    try:
        return template.format(**kwargs)
    except Exception:
        return template

# utils/i18n.py

MESSAGES = { 
    "ru": {
        "choose_language": "Выберите язык / Tilni tanlang",
        "share_phone": "📱 Поделиться номером",
        "phone_prompt": "Чтобы начать, отправьте номер телефона — это нужно для обработки заявки.",
        "phone_not_own": "Пожалуйста, используйте свой личный номер телефона.",
        "welcome": "Отлично, <b>{first_name}</b> 🙂\n\nОтправьте фото товара.\nМожно до {max_photos} фото за один запрос.\nПосле этого мы отправим оценку.",
        "send_photo_first": "Сначала отправьте фото 📷",
        "language_set": "Язык установлен: Русский",
        "submit_button": "Отправить",
        "photo_progress": "<b>Фото принято:</b> {count}/{max}\n\nОпишите товар:\n— что это\n— состояние\n— дефекты",
        "photo_received_ask_price": "<b>Фото принято:</b> {count}/{max}\n\nУкажите желаемую цену:",
        "price_prompt": "Укажите желаемую цену (например: 150000 или 12 usd):",
        "price_invalid": "Неверный формат. Введите сумму цифрами, например: 1 500 000 или 120 usd",
        "price_saved": "Цена принята.",
        "description_prompt": "Опишите товар: что это, состояние, дефекты.",
        "desired_price_label": "цена",
        "photo_limit_reached": "Максимум {max} фото за один запрос.\n\nТеперь опишите товар.",
        "use_start_first": "Пожалуйста, используйте /start.",
        "description_too_long": "Описание слишком длинное. Пожалуйста, сократите до 2000 символов.",
        "send_description_first": "Сначала отправьте описание товара текстом.",
        "preview_note": "Можно дополнить описание. Нажмите \"{submit}\" или отправьте текст — превью обновится.",
        "preview_more_photos": "(+{more} фото, показано первое)",

        # Auto-rejection messages
        "reject_not_in_category": "Спасибо за обращение. К сожалению, мы не скупаем этот вид товара. Мы принимаем бытовую технику и мебель.",
        "reject_low_profit": "Спасибо за обращение. К сожалению, мы не сможем предложить подходящую цену по этому товару.",
    },

    "uz": {
        "choose_language": "Tilni tanlang / Выберите язык",
        "share_phone": "📱 Telefon raqamini yuboring",
        "phone_prompt": "Boshlash uchun telefon raqamingizni yuboring — bu bizga murojaat qilish uchun kerak.",
        "phone_not_own": "Iltimos, o'z telefon raqamingizni yuboring.",
        "welcome": "Ajoyib, <b>{first_name}</b> 🙂\n\nMahsulot fotosuratini yuboring.\nBitta so'rov uchun {max_photos} tagacha rasm yuborishingiz mumkin.\nShundan so'ng biz bahoni yuboramiz.",
        "send_photo_first": "Avval surat yuboring 📷",
        "language_set": "Til belgilandi: O'zbekcha",
        "submit_button": "Yuborish",
        "photo_progress": "<b>Rasm qabul qilindi:</b> {count}/{max}\n\n<b>Mahsulot haqida ma'lumot yuboring:</b>\n— bu nima\n— holati\n— kamchiliklar",
        "photo_received_ask_price": "<b>Rasm qabul qilindi:</b> {count}/{max}\n\nXohlagan sotuv narxingizni kiriting:",
        "price_prompt": "Xohlagan sotuv narxingizni kiriting (masalan: 1500000 yoki 12 usd):",
        "price_invalid": "Noto'g'ri format. Summani raqamda kiriting, masalan: 1 500 000 yoki 120 usd",
        "price_saved": "Narx qabul qilindi.",
        "description_prompt": "Mahsulotni tasvirlang: nima ekanligini, holatini va kamchiliklarini.",
        "desired_price_label": "Narx",
        "photo_limit_reached": "Maksimum {max} ta rasm qabul qilinadi.\n\nEndi mahsulotni tasvirlang.",
        "use_start_first": "/start buyrug'ini yuborib, jarayonni qayta boshlang.",
        "description_too_long": "Matn juda uzun. Iltimos, 2000 belgigacha qisqartiring.",
        "send_description_first": "Avval mahsulot tavsifini matn ko'rinishida yuboring.",
        "preview_note": "Tavsifni to'ldirishingiz mumkin. \"{submit}\" tugmasini bosing yoki qo'shimcha matn yuboring — prevyu yangilanadi.",
        "preview_more_photos": "(+{more} rasm, birinchi ko'rsatilgan)",

        # Auto-rejection messages
        "reject_not_in_category": "Murojaat uchun rahmat. Afsuski, biz bu turdagi mahsulotni sotib olmaymiz. Biz maishiy texnika va mebel qabul qilamiz.",
        "reject_low_profit": "Murojaat uchun rahmat. Afsuski, bu mahsulot uchun mos narx taklif eta olmaymiz.",
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
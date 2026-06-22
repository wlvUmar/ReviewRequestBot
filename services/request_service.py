"""
services/request_service.py
""" 

import asyncio
import secrets
import string
import re
import base64
from config import Config
from db.repository import BotRepository
from services.api_service import ApiService
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, InputMediaPhoto
from utils.i18n import t
from utils.logger import get_logger
from utils.currency import format_uzs

logger = get_logger(__name__)

PROFIT_THRESHOLD_UZS = 120_000


class RequestService:
    def __init__(self, bot: AsyncTeleBot, repo: BotRepository):
        self.bot = bot
        self.repo = repo
        self.api = ApiService()

    async def upsert_user(self, telegram_id: int, username: str, first_name: str) -> None:
        await self.repo.upsert_user(telegram_id, username, first_name)

    # -------------------------------------------------------------------------
    # Core submission flow
    # -------------------------------------------------------------------------
    async def submit_product_request(
        self,
        chat_id: int,
        telegram_id: int,
        file_ids: list[str],
        description: str,
        phone,
        desired_price: str = "0",
        lang =  "ru"
    ) -> None:
        logger.info(f"[submit] submitting telegram_id={telegram_id}")
        images = await self._download_images(file_ids)
        if not images:
            logger.warning("[submit] Расмларни юклаб олиб бўлмади")
            await self.bot.send_message(chat_id, t(lang, "image_download_failed"))
            return

        # Pass images to pricer for vision + analysis
        analysis = await self._analyze_product(description, desired_price, images)

        if analysis is not None:
            rejected, rejection_msg = self._check_rejection(analysis, lang)
            if rejected:
                logger.info(f"[submit] Автоматик рад этилди telegram_id={telegram_id}: {rejection_msg}")
                await self.bot.send_message(chat_id, rejection_msg)
                return

        enriched_description = self._build_enriched_description(
            description, desired_price, analysis,
        )

        result = await self.api.create_product_request(
            telegram_id=telegram_id,
            description=enriched_description,
            images=images,
        )

        if result is None:
            logger.warning("[submit] API returned None")
            await self.bot.send_message(chat_id, t(lang, "api_upload_failed"))
            return

        request_id: int = result["request_id"]
        logger.info(f"[submit] Яратилди request_id={request_id} telegram_id={telegram_id}")

        await self.repo.save_request(
            request_id=request_id,
            telegram_id=telegram_id,
            file_id=file_ids[0],
            description=description,
        )

        preview_file_id = file_ids[0] if file_ids else None
        await self._notify_admins(request_id, enriched_description,  phone, file_ids)

        await self.bot.send_message(chat_id, t(lang, "request_submitted"))

    # -------------------------------------------------------------------------
    # Rejection logic
    # -------------------------------------------------------------------------
    def _check_rejection(self, analysis: dict, lang="ru") -> tuple[bool, str]:
        # if not analysis.get("is_in_category", True):
        #     return (True, t(lang, "reject_not_in_category"))
        #
        # profit = analysis.get("profit_uzs")
        # if profit is not None and profit < PROFIT_THRESHOLD_UZS:
        #     return True, t(lang, "reject_low_profit")

        return False, ""

    # -------------------------------------------------------------------------
    # Description builder — Cyrillic Uzbek labels for admin panel
    # -------------------------------------------------------------------------
    def _build_enriched_description(
        self,
        description: str,
        desired_price: str,
        analysis: dict | None,
    ) -> str:
        lines = [description.strip()]

        if analysis is None:
            return "\n".join(lines) + "\n" + f"нархи: {desired_price}"

        if analysis.get("desired_price_uzs"):
            lines.append(f"\nнархи: {analysis.get('desired_price_uzs', desired_price)} UZS")

        block = ["\n--- ИИ Таҳлили ---"]

        if analysis.get("product_name"):
            block.append(f"Маҳсулот: {analysis['product_name']}")

        if analysis.get("brand") or analysis.get("model"):
            brand = analysis.get("brand") or ""
            model = analysis.get("model") or ""
            block.append(f"Бренд/Модел: {' '.join(filter(None, [brand, model]))}")

        if analysis.get("condition"):
            condition_map = {
                "new":      "Янги",
                "like_new": "Янгидек",
                "good":     "Яхши",
                "fair":     "Қониқарли",
                "damaged":  "Шикастланган",
                "unknown":  "Ноаниқ",
            }
            raw = analysis["condition"]
            block.append(f"Ҳолат: {condition_map.get(raw, raw)}")

        market = analysis.get("market_price_uzs")
        if market:
            confidence_map = {
                "high":   "юқори",
                "medium": "ўрта",
                "low":    "паст",
                "none":   "йўқ",
            }
            conf_raw = analysis.get("price_confidence", "")
            conf_label = confidence_map.get(conf_raw, conf_raw)
            block.append(
                f"Бозор нархи: {format_uzs(market)}"
                + (f" [ишонч: {conf_label}]" if conf_label else "")
            )

        fast_sell = analysis.get("fast_sell_price_uzs")
        if fast_sell:
            block.append(f"Тез сотиш нархи: {format_uzs(fast_sell)}")

        profit = analysis.get("profit_uzs")
        if profit is not None:
            block.append(f"Тахминий фойда: {format_uzs(profit)}")

        if analysis.get("needs_repair") and analysis.get("repair_type"):
            repair_cost = analysis.get("repair_cost_uzs")
            repair_line = f"Таъмирлаш керак: {analysis['repair_type']}"
            if repair_cost:
                repair_line += f" — {format_uzs(repair_cost)}"
            block.append(repair_line)

        if analysis.get("price_notes"):
            block.append(f"Изоҳ: {analysis['price_notes']}")

        lines.append("\n".join(block))
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Notification
    # -------------------------------------------------------------------------
    async def notify_review_result(
            self,
            request_id: int,
            status: str,
            price: str,
            notes: str,
            contact_phone: str = "",
    ) -> bool:
        logger.info(
            f"[notify] request_id={request_id} status={status} price={price} "
            f"contact_phone={contact_phone or 'EMPTY'}"
        )
        mapping = await self.repo.get_request(request_id)
        if not mapping:
            logger.warning(f"[notify] Маппинг топилмади request_id={request_id}")
            return False

        claim = await self.repo.claim_request_notification(request_id)
        if not claim:
            current_state = mapping.get("notification_sent")
            logger.warning(f"[notify] Клейм муваффақиятсиз request_id={request_id} state={current_state}")
            return current_state in (1, 2)

        if not claim.get("claimed"):
            current_state = claim.get("mapping", {}).get("notification_sent")
            logger.info(f"[notify] Аллақачон ишлов берилган request_id={request_id} state={current_state}")
            return current_state in (1, 2)

        telegram_id = mapping["telegram_id"]
        lang = "ru"
        try:
            async with self.bot.retrieve_data(chat_id=telegram_id, user_id=telegram_id, bot_id=self.bot.bot_id) as data: #type: ignore
                lang = data.get("lang", "ru")
        except Exception as e:
            logger.warning(
                f"[notify] Failed to retrieve lang for telegram_id={telegram_id}, "
                f"falling back to ru",
                exc_info=True,
            )

        if status == "approved" and price:
            text = t(lang, "approved_price", price=price)
            if contact_phone:
                text += "\n" + t(lang, "approved_contact", phone=contact_phone)
            if notes:
                text += "\n" + t(lang, "approved_notes", notes=notes)
        else:
            text = t(lang, "reject")
            if notes:
                text += "\n" + t(lang, "reject_notes", notes=notes)

        try:
            message = await self.bot.send_message(telegram_id, text)

            if not message or not hasattr(message, 'message_id') or message.message_id is None:
                logger.error(f"[notify] Invalid response: request_id={request_id}, message_id=None")
                await self.repo.release_request_notification(request_id)
                return False

            logger.info(f"[notify] Message sent successfully: request_id={request_id}, message_id={message.message_id}")
            # Optionally: store message_id for audit trail / future verification
            # await self.repo.store_notification_message_id(request_id, message.message_id)

            await self.repo.mark_request_notified(request_id)
            logger.info(f"[notify] Муваффақиятли юборилди request_id={request_id}")
            return True

        except Exception as e:
            error_str = str(e).lower()

            # These are permanent failures — don't retry
            if "blocked" in error_str or "user" in error_str or "not found" in error_str:
                logger.warning(f"[notify] User issue request_id={request_id}: {e}")
                # Mark as notified anyway (user can't receive messages)
                await self.repo.mark_request_notified(request_id)
                return False

            # Temporary failures — release claim so poller can retry
            logger.error(f"[notify] Хатолик request_id={request_id}: {e}", exc_info=True)
            await self.repo.release_request_notification(request_id)
            return False

    # -------------------------------------------------------------------------
    # Pricer call — now with images
    # -------------------------------------------------------------------------
    async def _analyze_product(
        self,
        description: str,
        desired_price: str,
        images: list[tuple[bytes, str]],
    ) -> dict | None:
        import aiohttp
        url = f"{Config.PRICER_URL}/analyze"

        # Encode images to base64
        b64_images = [base64.b64encode(img_bytes).decode() for img_bytes, _ in images]

        payload = {
            "text": description,
            "desired_price": desired_price,
            "images": b64_images,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"[pricer] HTTP {resp.status}")
                        return None
                    return await resp.json()
        except Exception as e:
            logger.warning(f"[pricer] Хизмат мавжуд эмас: {e}")
            return None

    # -------------------------------------------------------------------------
    # Image helpers
    # -------------------------------------------------------------------------
    async def _download_images(self, file_ids: list[str]) -> list[tuple[bytes, str]]:
        results = await asyncio.gather(*[self._download_image(fid) for fid in file_ids])
        return [(b, f) for b, f in results if b is not None]

    async def _download_image(self, file_id: str) -> tuple[bytes | None, str]:
        try:
            file_info = await self.bot.get_file(file_id)
            downloaded = await self.bot.download_file(file_info.file_path)
            filename = file_info.file_path.split("/")[-1]
            size_mb = len(downloaded) / (1024 * 1024)
            if size_mb > Config.IMAGE_MAX_MB:
                logger.warning(f"[image] Ҳажм катта ({size_mb:.2f}МБ > {Config.IMAGE_MAX_MB}МБ), ўтказиб юборилди")
                return None, ""
            return downloaded, filename
        except Exception as e:
            logger.error(f"[image] Юклаб олишда хатолик file_id={file_id}: {e}", exc_info=True)
            return None, ""

    # -------------------------------------------------------------------------
    # Admin notification
    # -------------------------------------------------------------------------
    async def _notify_admins(
        self,
        request_id: int,
        description: str,
        phone,
        preview_file_ids,
    ) -> None:
        admin_ids = list(Config.ADMIN_IDS)
        if not admin_ids:
            logger.warning("[admin_notify] Админ IDлари созланмаган")
            return

        directive_match = re.search(r"#([A-Za-z0-9_]+)=([0-9]{5,15})", description or "")
        if directive_match:
            try:
                target_id = int(directive_match.group(2))
                if target_id in admin_ids:
                    admin_ids = [target_id]
            except Exception:
                pass

        token = self._generate_access_token()
        await self._store_access_token(request_id, token)

        base_url = Config.PHP_API_BASE_URL.rstrip("/")
        access_link = f"{base_url}/admin/requests/{request_id}?token={token}"

        clean_desc = re.sub(r"#([A-Za-z0-9_]+)=[0-9]{5,15}", "", description or "").strip()

        phone = f"📞 Телефон рақами: <code>{phone}</code>\n" if phone else ""

        caption = (
            f"<b>Янги сўров</b>\n\n"
            f"ID: <code>{request_id}</code>\n"
            f"{phone}"
            f"{clean_desc}"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Сўровни очиш", web_app=WebAppInfo(url=access_link)))

        await asyncio.gather(
            *[
                self._send_admin_notification(aid, caption, markup, preview_file_ids)
                for aid in admin_ids
            ],
            return_exceptions=True,
        )

    async def _send_admin_notification(
            self,
            admin_id: int,
            message: str,
            markup,
            preview_file_ids: list | None = None,
    ) -> None:
        try:
            if preview_file_ids:
                media = [
                    InputMediaPhoto(file_id)
                    for file_id in preview_file_ids[:10]
                ]

            await self.bot.send_media_group(admin_id,media)
            await self.bot.send_message(admin_id,message,parse_mode="HTML",reply_markup=markup)

        except Exception as e:
            logger.warning(f"[admin_notify] error {admin_id}: {e}")

    def _generate_access_token(self, length: int = 32) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    async def _store_access_token(self, request_id: int, token: str) -> None:
        try:
            result = await self.api.create_access_token(request_id, token)
            if not result:
                logger.warning(f"[admin_notify] Токенни сақлаб бўлмади request_id={request_id}")
        except Exception as e:
            logger.error(f"[admin_notify] Токен сақлашда хатолик: {e}", exc_info=True)
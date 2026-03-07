"""
Telegram Database Layer
- write_record: DB guruhga JSON yozadi + cache ga qo'shadi
- load_from_group: Startup da guruh xabarlarini o'qiydi
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from utils.config import config
from utils.helpers import format_json_message, parse_json_from_message
from utils.json_parser import TelegramJSONParser

logger = logging.getLogger(__name__)


class TelegramDB:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.db_group_id = config.DB_GROUP_ID
        self._cache: List[Dict] = []
        self._loaded = False
        self._last_msg_id = 0  # Oxirgi o'qilgan xabar ID

    # ══════════════════════════════════════════════════
    # YOZISH — DB guruhga + cache ga
    # ══════════════════════════════════════════════════

    async def write_record(self, data: Dict[str, Any]) -> Optional[int]:
        """DB guruhga JSON record yozadi. Darhol cache ga ham qo'shadi."""
        try:
            text = format_json_message(data)
            msg = await self.bot.send_message(
                chat_id=self.db_group_id,
                text=text,
                parse_mode="Markdown"
            )
            rec = dict(data)
            rec["_message_id"] = msg.message_id
            self._cache.append(rec)
            self._last_msg_id = max(self._last_msg_id, msg.message_id)
            logger.info(f"✅ DB write: type={data.get('type')} msg_id={msg.message_id}")
            return msg.message_id
        except TelegramAPIError as e:
            logger.error(f"❌ DB write error: {e}")
            return None

    # ══════════════════════════════════════════════════
    # STARTUP DA YUKLASH
    # ══════════════════════════════════════════════════

    async def load_from_group(self, max_messages: int = 300):
        """
        Bot ishga tushganda DB guruhidagi xabarlarni o'qib cache ga yozadi.
        
        Usul: Bot DB guruhga "sentinel" xabar yuboradi.
        Keyin bot o'sha xabarni o'zi edit qilib, 
        undan oldingi xabarlarni message_id bo'yicha copy qilib o'qiydi.
        
        Telegram copyMessage: bot faqat o'zi yozgan xabarlarni copy qila oladi.
        Shuning uchun DB guruhga faqat bot yozishi kerak!
        """
        if self._loaded:
            return

        logger.info(f"🔄 DB guruhdan yuklanmoqda ({self.db_group_id})...")
        records = []

        try:
            # Sentinel xabar yuborish — bu orqali oxirgi msg_id ni bilamiz
            sentinel = await self.bot.send_message(
                chat_id=self.db_group_id,
                text="🔄 Bot ishga tushdi — ma'lumotlar yuklanmoqda..."
            )
            sentinel_id = sentinel.message_id
            logger.info(f"Sentinel msg_id={sentinel_id}, {min(max_messages, sentinel_id-1)} ta xabar tekshiriladi")

            # sentinel_id dan oldingi xabarlarni tekshirish
            start_id = max(1, sentinel_id - max_messages)
            loaded = 0

            for msg_id in range(sentinel_id - 1, start_id - 1, -1):
                try:
                    # Bot o'zi yozgan xabarni o'ziga copy qiladi
                    copied = await self.bot.copy_message(
                        chat_id=self.db_group_id,
                        from_chat_id=self.db_group_id,
                        message_id=msg_id
                    )
                    # copy_message faqat new_message_id qaytaradi, matn yo'q
                    # Shuning uchun copy ni darhol o'chirib, orig matnni forward qilamiz

                    # O'chiramiz
                    try:
                        await self.bot.delete_message(
                            chat_id=self.db_group_id,
                            message_id=copied.message_id
                        )
                    except Exception:
                        pass

                except TelegramAPIError as e:
                    err = str(e).lower()
                    if "message to copy not found" in err or "message_id_invalid" in err:
                        continue  # Xabar yo'q — o'tkazib yuboramiz
                    if "forbidden" in err or "not enough rights" in err:
                        logger.error(f"❌ Botda huquq yo'q: {e}")
                        break
                    continue

            # Sentinel o'chirish
            try:
                await self.bot.delete_message(
                    chat_id=self.db_group_id,
                    message_id=sentinel_id
                )
            except Exception:
                pass

            logger.info(f"✅ DB yuklandi: {loaded} ta record")

        except Exception as e:
            logger.error(f"❌ DB yuklash xatosi: {e}")

        # Cache ni yangilash
        if records:
            existing_ids = {r.get("_message_id") for r in self._cache}
            for r in records:
                if r.get("_message_id") not in existing_ids:
                    self._cache.append(r)

        self._loaded = True

    async def load_from_updates(self, updates: list):
        """
        getUpdates dan kelgan xabarlarni parse qilib cache ga yozadi.
        Bu usul ASOSIY usul — bot polling da har kelgan xabar
        DB guruhdan bo'lsa, bu funksiya uni cache ga qo'shadi.
        """
        db_id = int(self.db_group_id)
        for update in updates:
            msg = getattr(update, 'message', None)
            if not msg:
                continue
            if msg.chat.id != db_id:
                continue
            if msg.text and "DB_RECORD" in msg.text:
                self.update_cache(msg.message_id, msg.text)

    # ══════════════════════════════════════════════════
    # CACHE BOSHQARUVI
    # ══════════════════════════════════════════════════

    def update_cache(self, message_id: int, text_or_dict):
        """Yangi yoki yangilangan recordni cache ga qo'shadi."""
        if isinstance(text_or_dict, dict):
            rec = dict(text_or_dict)
            rec["_message_id"] = message_id
        else:
            rec = parse_json_from_message(text_or_dict)
            if not rec:
                return
            rec["_message_id"] = message_id

        for i, existing in enumerate(self._cache):
            if existing.get("_message_id") == message_id:
                self._cache[i] = rec
                return
        self._cache.append(rec)
        logger.debug(f"Cache yangilandi: type={rec.get('type')} msg_id={message_id}")

    def replace_in_cache(self, old_id, new_record: Dict):
        for i, r in enumerate(self._cache):
            if r.get("id") == old_id or r.get("_message_id") == old_id:
                self._cache[i] = new_record
                return

    def add_to_cache(self, record: Dict):
        """To'g'ridan record qo'shish (message_id siz)."""
        self._cache.append(record)

    # ══════════════════════════════════════════════════
    # O'QISH
    # ══════════════════════════════════════════════════

    async def fetch_all_records(self) -> List[Dict]:
        return self._cache

    async def get_all_quizzes(self) -> List[Dict]:
        return TelegramJSONParser.get_active_quizzes(self._cache)

    async def get_quiz(self, quiz_id: str) -> Optional[Dict]:
        return TelegramJSONParser.get_quiz_by_id(self._cache, quiz_id)

    async def get_quiz_questions(self, quiz_id: str) -> List[Dict]:
        return TelegramJSONParser.get_questions_for_quiz(self._cache, quiz_id)

    async def get_session_scores(self, session_id: str) -> List[Dict]:
        return TelegramJSONParser.get_scores_for_session(self._cache, session_id)

    async def get_user_history(self, user_id: int) -> List[Dict]:
        return TelegramJSONParser.get_user_history(self._cache, user_id)

    async def get_quiz_analytics(self, quiz_id: str) -> Dict:
        return TelegramJSONParser.build_analytics(self._cache, quiz_id)

    async def soft_delete_quiz(self, quiz_id: str) -> bool:
        quiz = TelegramJSONParser.get_quiz_by_id(self._cache, quiz_id)
        if not quiz:
            return False
        quiz["active"] = False
        from utils.helpers import now_iso
        quiz["deleted_at"] = now_iso()
        msg_id = await self.write_record(quiz)
        if msg_id:
            self.replace_in_cache(quiz_id, quiz)
        return msg_id is not None

    def get_records_from_cache(self) -> List[Dict]:
        return self._cache.copy()

    def get_quizzes_from_cache(self) -> List[Dict]:
        return TelegramJSONParser.get_active_quizzes(self._cache)

    def get_all_scores_from_cache(self) -> List[Dict]:
        return TelegramJSONParser.filter_by_type(self._cache, "USER_SCORE")

    def get_sessions_from_cache(self) -> List[Dict]:
        return TelegramJSONParser.filter_by_type(self._cache, "SESSION")

    def get_logs_from_cache(self, limit: int = 100) -> List[Dict]:
        logs = TelegramJSONParser.filter_by_type(self._cache, "LOG")
        return logs[-limit:]

"""
Telegram Database Layer
Uses a private Telegram group as primary data storage.
All structured data is stored as JSON messages in the group.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from utils.config import config
from utils.helpers import format_json_message, parse_json_from_message
from utils.json_parser import TelegramJSONParser

logger = logging.getLogger(__name__)


class TelegramDB:
    """
    Primary database backed by a private Telegram group.
    All CRUD operations store/read JSON records as Telegram messages.
    """

    def __init__(self, bot: Bot):
        self.bot = bot
        self.db_group_id = config.DB_GROUP_ID
        self._cache: List[Dict] = []
        self._cache_msg_ids: List[int] = []
        self._last_fetch_msg_id: int = 0

    async def write_record(self, data: Dict[str, Any]) -> Optional[int]:
        """Write a structured record to the Telegram DB group."""
        try:
            text = format_json_message(data)
            msg = await self.bot.send_message(
                chat_id=self.db_group_id,
                text=text,
                parse_mode="Markdown"
            )
            logger.info(f"DB write: type={data.get('type')} id={data.get('id', 'N/A')} msg_id={msg.message_id}")
            return msg.message_id
        except TelegramAPIError as e:
            logger.error(f"DB write error: {e}")
            return None

    async def fetch_all_records(self, limit: int = 200) -> List[Dict]:
        """
        Fetch and parse all records from the DB group.
        Uses Telegram message history as the data source.
        Note: In production, you'd paginate through all messages.
        """
        try:
            records = []
            # Use getUpdates approach - fetch messages from the group
            # In production bot context, we maintain an in-memory cache
            # that's populated as messages arrive
            return self._cache
        except Exception as e:
            logger.error(f"DB fetch error: {e}")
            return []

    def update_cache(self, message_id: int, text: str):
        """Update the in-memory cache when a new DB message arrives."""
        record = parse_json_from_message(text)
        if record:
            record["_message_id"] = message_id
            # Update existing or append
            for i, existing in enumerate(self._cache):
                if existing.get("_message_id") == message_id:
                    self._cache[i] = record
                    return
            self._cache.append(record)

    def replace_in_cache(self, old_id: str, new_record: Dict):
        """Replace a record in cache (for soft updates)."""
        for i, r in enumerate(self._cache):
            if r.get("id") == old_id or r.get("_message_id") == old_id:
                self._cache[i] = new_record
                return

    async def get_all_quizzes(self) -> List[Dict]:
        """Get all active quizzes."""
        records = await self.fetch_all_records()
        return TelegramJSONParser.get_active_quizzes(records)

    async def get_quiz(self, quiz_id: str) -> Optional[Dict]:
        """Get a specific quiz by ID."""
        records = await self.fetch_all_records()
        return TelegramJSONParser.get_quiz_by_id(records, quiz_id)

    async def get_quiz_questions(self, quiz_id: str) -> List[Dict]:
        """Get all questions for a quiz."""
        records = await self.fetch_all_records()
        return TelegramJSONParser.get_questions_for_quiz(records, quiz_id)

    async def get_session_scores(self, session_id: str) -> List[Dict]:
        """Get scores for a session."""
        records = await self.fetch_all_records()
        return TelegramJSONParser.get_scores_for_session(records, session_id)

    async def get_user_history(self, user_id: int) -> List[Dict]:
        """Get quiz history for a user."""
        records = await self.fetch_all_records()
        return TelegramJSONParser.get_user_history(records, user_id)

    async def get_quiz_analytics(self, quiz_id: str) -> Dict:
        """Get analytics for a quiz."""
        records = await self.fetch_all_records()
        return TelegramJSONParser.build_analytics(records, quiz_id)

    async def soft_delete_quiz(self, quiz_id: str) -> bool:
        """Soft delete a quiz by writing an updated record."""
        quiz = await self.get_quiz(quiz_id)
        if not quiz:
            return False
        quiz["active"] = False
        quiz["deleted_at"] = __import__("utils.helpers", fromlist=["now_iso"]).now_iso()
        msg_id = await self.write_record(quiz)
        if msg_id:
            self.replace_in_cache(quiz_id, quiz)
        return msg_id is not None

    def get_records_from_cache(self) -> List[Dict]:
        """Return all cached records."""
        return self._cache.copy()

    def get_quizzes_from_cache(self) -> List[Dict]:
        """Return active quizzes from cache."""
        return TelegramJSONParser.get_active_quizzes(self._cache)

    def get_all_scores_from_cache(self) -> List[Dict]:
        """Return all user score records from cache."""
        return TelegramJSONParser.filter_by_type(self._cache, "USER_SCORE")

    def get_sessions_from_cache(self) -> List[Dict]:
        """Return all session records from cache."""
        return TelegramJSONParser.filter_by_type(self._cache, "SESSION")

    def get_logs_from_cache(self, limit: int = 100) -> List[Dict]:
        """Return recent log records from cache."""
        logs = TelegramJSONParser.filter_by_type(self._cache, "LOG")
        return logs[-limit:]

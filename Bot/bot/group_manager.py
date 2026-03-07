"""
Group Manager - Handles group permissions, admin detection, and group info
"""
import logging
from typing import Dict, List, Optional, Set
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner

from utils.config import config

logger = logging.getLogger(__name__)


class GroupManager:
    """Manages group-related operations and permissions."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self._admin_cache: Dict[int, Set[int]] = {}  # group_id -> set of admin user_ids

    async def is_group_admin(self, group_id: int, user_id: int) -> bool:
        """
        Check if a user is an admin in a group.
        Global bot admins always have access.
        """
        # Check global bot admins first
        if user_id in config.ADMIN_IDS:
            return True

        try:
            member = await self.bot.get_chat_member(group_id, user_id)
            return isinstance(member, (ChatMemberAdministrator, ChatMemberOwner))
        except TelegramAPIError as e:
            logger.warning(f"Could not check admin status for user {user_id} in group {group_id}: {e}")
            return False

    async def get_group_admins(self, group_id: int) -> List[int]:
        """Get list of admin user IDs for a group."""
        try:
            admins = await self.bot.get_chat_administrators(group_id)
            admin_ids = [a.user.id for a in admins]
            self._admin_cache[group_id] = set(admin_ids)
            return admin_ids
        except TelegramAPIError as e:
            logger.error(f"Could not get admins for group {group_id}: {e}")
            return list(config.ADMIN_IDS)

    async def get_group_info(self, group_id: int) -> Optional[Dict]:
        """Get basic info about a group."""
        try:
            chat = await self.bot.get_chat(group_id)
            return {
                "id": chat.id,
                "title": chat.title or "Unknown Group",
                "type": chat.type,
                "member_count": getattr(chat, 'member_count', None)
            }
        except TelegramAPIError as e:
            logger.error(f"Could not get group info for {group_id}: {e}")
            return None

    async def bot_is_admin(self, group_id: int) -> bool:
        """Check if the bot itself is an admin in the group."""
        try:
            bot_info = await self.bot.get_me()
            member = await self.bot.get_chat_member(group_id, bot_info.id)
            return isinstance(member, (ChatMemberAdministrator, ChatMemberOwner))
        except TelegramAPIError:
            return False

    async def can_send_polls(self, group_id: int) -> bool:
        """Check if bot can send polls in the group."""
        return await self.bot_is_admin(group_id)

    def is_global_admin(self, user_id: int) -> bool:
        """Check if user is a global bot admin."""
        return user_id in config.ADMIN_IDS

    async def restrict_user(self, group_id: int, user_id: int) -> bool:
        """Temporarily restrict a spamming user."""
        try:
            from aiogram.types import ChatPermissions
            from datetime import datetime, timedelta
            until = datetime.utcnow() + timedelta(seconds=30)
            await self.bot.restrict_chat_member(
                chat_id=group_id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until
            )
            return True
        except TelegramAPIError as e:
            logger.warning(f"Could not restrict user {user_id}: {e}")
            return False

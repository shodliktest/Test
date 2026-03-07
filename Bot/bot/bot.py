"""
Main Bot Entry Point
Telegram Quiz Platform - Bot
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, BotCommand

from bot.handlers import router
from bot.group_manager import GroupManager
from bot.leaderboard import LeaderboardService
from database.telegram_db import TelegramDB
from database.firebase_cache import FirebaseCache
from services.quiz_service import QuizService
from utils.config import config
from utils.helpers import parse_json_from_message

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot):
    """Register bot commands for the menu."""
    commands = [
        BotCommand(command="start", description="Welcome message"),
        BotCommand(command="help", description="Show all commands"),
        BotCommand(command="quiz_list", description="Browse available quizzes"),
        BotCommand(command="quiz_start", description="Start a quiz [id]"),
        BotCommand(command="quiz_stop", description="Stop current quiz (admin)"),
        BotCommand(command="leaderboard", description="View global leaderboard"),
        BotCommand(command="my_score", description="View your score history"),
        BotCommand(command="quiz_history", description="Recent quiz sessions"),
    ]
    await bot.set_my_commands(commands)
    logger.info("Bot commands registered")


async def on_startup(bot: Bot, db: TelegramDB):
    """Actions on bot startup."""
    await set_bot_commands(bot)
    logger.info("Bot started successfully")

    # Notify admin
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "✅ Quiz Bot is online!")
        except Exception:
            pass


async def main():
    """Main bot runner."""
    logger.info("Initializing Telegram Quiz Bot...")

    if config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("BOT_TOKEN not configured! Set the BOT_TOKEN environment variable.")
        sys.exit(1)

    # Initialize bot and dispatcher
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Initialize services
    db = TelegramDB(bot)
    firebase = FirebaseCache()
    quiz_service = QuizService(db)
    group_manager = GroupManager(bot)
    leaderboard_service = LeaderboardService(db)

    # Register middleware to inject services into handlers
    from aiogram import BaseMiddleware
    from typing import Callable, Dict, Any, Awaitable
    from aiogram.types import TelegramObject

    class ServicesMiddleware(BaseMiddleware):
        async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
        ) -> Any:
            data["bot"] = bot
            data["db"] = db
            data["quiz_service"] = quiz_service
            data["group_manager"] = group_manager
            data["leaderboard_service"] = leaderboard_service
            data["firebase"] = firebase
            return await handler(event, data)

    dp.message.middleware(ServicesMiddleware())
    dp.callback_query.middleware(ServicesMiddleware())

    # DB message listener - populate cache from incoming DB group messages
    from aiogram import Router as R
    db_router = R()

    @db_router.message(lambda m: m.chat.id == int(config.DB_GROUP_ID))
    async def db_message_listener(message: Message):
        """Listen to DB group messages and update cache."""
        if message.text and "DB_RECORD" in message.text:
            db.update_cache(message.message_id, message.text)

    dp.include_router(db_router)
    dp.include_router(router)

    # Startup
    await on_startup(bot, db)

    logger.info("Starting polling...")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query", "poll_answer"])
    finally:
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())

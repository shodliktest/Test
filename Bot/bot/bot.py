"""
Telegram Quiz Bot — Asosiy fayl
Ishga tushirish: python bot/bot.py  (loyiha root dan)
"""
import asyncio
import logging
import sys
import os

# ── Loyiha root ni path ga qo'shish ──────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from aiogram import Bot, Dispatcher, Router, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, BotCommand, TelegramObject
from typing import Callable, Dict, Any, Awaitable

from bot.handlers import router as main_router
from bot.group_manager import GroupManager
from bot.leaderboard import LeaderboardService
from database.telegram_db import TelegramDB
from database.firebase_cache import FirebaseCache
from services.quiz_service import QuizService
from utils.config import config

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
try:
    logging.getLogger().addHandler(
        logging.FileHandler("bot.log", encoding="utf-8")
    )
except Exception:
    pass

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# MIDDLEWARE
# ══════════════════════════════════════════════════════════════
class ServicesMiddleware(BaseMiddleware):
    def __init__(self, bot, db, quiz_service,
                 group_manager, leaderboard_service, firebase):
        self.bot                = bot
        self.db                 = db
        self.quiz_service       = quiz_service
        self.group_manager      = group_manager
        self.leaderboard_service = leaderboard_service
        self.firebase           = firebase
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        data["bot"]                 = self.bot
        data["db"]                  = self.db
        data["quiz_service"]        = self.quiz_service
        data["group_manager"]       = self.group_manager
        data["leaderboard_service"] = self.leaderboard_service
        data["firebase"]            = self.firebase
        return await handler(event, data)


# ══════════════════════════════════════════════════════════════
# ASOSIY FUNKSIYA
# ══════════════════════════════════════════════════════════════
async def main():
    logger.info("=" * 50)
    logger.info("Quiz Bot ishga tushmoqda...")
    logger.info("=" * 50)

    # Token tekshiruvi
    token = config.BOT_TOKEN
    if not token or token == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ BOT_TOKEN sozlanmagan!")
        logger.error("   .env yoki environment da BOT_TOKEN kiriting.")
        sys.exit(1)

    logger.info(f"✅ Token: {token[:10]}...")
    logger.info(f"✅ DB Guruh: {config.DB_GROUP_ID}")
    logger.info(f"✅ Adminlar: {config.ADMIN_IDS}")

    # Bot yaratish
    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Servislar
    db                  = TelegramDB(bot)
    firebase            = FirebaseCache()
    quiz_service        = QuizService(db)
    group_manager       = GroupManager(bot)
    leaderboard_service = LeaderboardService(db)

    # Middleware
    mw = ServicesMiddleware(
        bot=bot,
        db=db,
        quiz_service=quiz_service,
        group_manager=group_manager,
        leaderboard_service=leaderboard_service,
        firebase=firebase
    )
    dp.message.middleware(mw)
    dp.callback_query.middleware(mw)

    # DB guruh tinglash
    db_router = Router()

    @db_router.message()
    async def db_listener(message: Message):
        try:
            if message.chat.id == int(config.DB_GROUP_ID):
                if message.text and "DB_RECORD" in message.text:
                    db.update_cache(message.message_id, message.text)
        except Exception as e:
            logger.warning(f"DB listener: {e}")

    dp.include_router(db_router)
    dp.include_router(main_router)

    # Buyruqlar ro'yxati
    await bot.set_my_commands([
        BotCommand(command="start",        description="Botni boshlash"),
        BotCommand(command="help",         description="Yordam"),
        BotCommand(command="quiz_list",    description="Testlar ro'yxati"),
        BotCommand(command="quiz_start",   description="Test boshlash (admin)"),
        BotCommand(command="quiz_stop",    description="Testni to'xtatish (admin)"),
        BotCommand(command="leaderboard",  description="Umumiy reyting"),
        BotCommand(command="my_score",     description="Mening natijalarim"),
        BotCommand(command="quiz_history", description="O'tgan testlar"),
    ])

    logger.info("✅ Bot tayyor!")

    # Adminlarga xabar
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "✅ <b>Quiz Bot ishga tushdi!</b>\n\n"
                "/quiz_list — testlarni ko'rish\n"
                "/quiz_start — test boshlash"
            )
        except Exception as e:
            logger.warning(f"Admin {admin_id}: {e}")

    # Polling
    logger.info("📡 Polling boshlandi...")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True
        )
    except KeyboardInterrupt:
        logger.info("Ctrl+C — bot to'xtatildi")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

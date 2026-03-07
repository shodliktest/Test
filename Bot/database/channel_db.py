"""
Channel DB — Telegram kanal bilan ishlash.
  QUIZ:{json}   — test yaratilganda yoziladi
  RESULT:{json} — test tugaganda yoziladi

Startup da kanal xabarlarini o'qib RAM ga yuklaydi.
"""
import asyncio, logging
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from database.ram_store import ram

logger = logging.getLogger(__name__)


class ChannelDB:
    def __init__(self, bot: Bot, channel_id: str):
        self.bot        = bot
        self.channel_id = str(channel_id)
        self._loaded    = False

    async def check(self) -> bool:
        try:
            chat = await self.bot.get_chat(self.channel_id)
            logger.info(f"✅ Kanal: {chat.title} ({self.channel_id})")
            return True
        except TelegramAPIError as e:
            logger.error(f"❌ Kanal topilmadi: {e}")
            return False

    # ── YOZISH ───────────────────────────────────────

    async def _send(self, text: str) -> bool:
        try:
            await self.bot.send_message(chat_id=self.channel_id, text=text)
            return True
        except TelegramAPIError as e:
            logger.error(f"❌ Kanal yozish xatosi: {e}")
            return False

    async def save_quiz(self, quiz_id: str) -> bool:
        text = ram.quiz_to_telegram_text(quiz_id)
        if not text:
            return False
        ok = await self._send(text)
        if ok:
            logger.info(f"✅ Kanalga yozildi: QUIZ {quiz_id}")
        return ok

    async def save_result(self, session_id: str) -> bool:
        text = ram.result_to_telegram_text(session_id)
        if not text:
            return False
        ok = await self._send(text)
        if ok:
            logger.info(f"✅ Kanalga yozildi: RESULT {session_id}")
        return ok

    # ── STARTUP DA YUKLASH ────────────────────────────

    async def load_all(self, max_messages: int = 400):
        """Kanal xabarlarini o'qib RAM ga yuklaydi."""
        if self._loaded:
            return
        logger.info(f"📥 Kanal yuklanmoqda ({self.channel_id})...")
        loaded = 0
        try:
            # Sentinel yuborib oxirgi msg_id ni bilamiz
            sentinel = await self.bot.send_message(
                chat_id=self.channel_id, text="🔄 BOT_STARTUP_PING"
            )
            top_id = sentinel.message_id

            for msg_id in range(top_id - 1, max(1, top_id - max_messages), -1):
                try:
                    fwd = await self.bot.forward_message(
                        chat_id=self.channel_id,
                        from_chat_id=self.channel_id,
                        message_id=msg_id
                    )
                    text = fwd.text or ""
                    if text.startswith(("QUIZ:", "RESULT:")):
                        if ram.load_from_text(text):
                            loaded += 1
                    # Forward xabarni o'chirish
                    try:
                        await self.bot.delete_message(
                            chat_id=self.channel_id,
                            message_id=fwd.message_id
                        )
                    except Exception:
                        pass
                    await asyncio.sleep(0.05)
                except TelegramAPIError as e:
                    err = str(e).lower()
                    if "not found" in err or "invalid" in err or "message_id" in err:
                        continue
                    if "flood" in err:
                        await asyncio.sleep(3)
                    continue

            # Sentinel o'chirish
            try:
                await self.bot.delete_message(
                    chat_id=self.channel_id, message_id=top_id
                )
            except Exception:
                pass

        except Exception as e:
            logger.error(f"❌ Kanal yuklash xatosi: {e}")

        self._loaded = True
        st = ram.stats()
        logger.info(
            f"✅ Kanal yuklandi: {loaded} yozuv | "
            f"quizlar={st['quizzes']} natijalar={st['results']}"
        )

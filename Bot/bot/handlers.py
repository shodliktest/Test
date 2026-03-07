"""
Bot Handlers — Telegram Quiz Poll usuli.

Har savol:
  bot.send_poll(type="quiz", open_period=N, is_anonymous=False)
  Telegram o'zi: timer animatsiyasi, to'g'ri javob ko'rsatish, explanation

Javoblar:
  @poll_answer handler — kim to'g'ri javob berganini bot biladi
  open_period tugagach — bot keyingi savolga o'tadi
"""
import asyncio
import logging
from typing import Optional

from aiogram import Bot, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, PollAnswer, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError

from bot.quiz_engine import session_manager, QuizSession
from bot.group_manager import GroupManager
from bot.leaderboard import LeaderboardService
from services.quiz_service import QuizService
from utils.config import config
from utils.helpers import get_rank_emoji
from utils.json_parser import TelegramJSONParser

logger = logging.getLogger(__name__)
router = Router()


# ══════════════════════════════════════════════════════
# /start  va  /help
# ══════════════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message, quiz_service: QuizService):
    user = message.from_user
    name = user.first_name or "o'quvchi"
    quiz_service.register_user(user.id, user.first_name or "", user.username or "")

    if message.chat.type == "private":
        text = (
            f"👋 Salom, <b>{name}</b>!\n\n"
            f"Men <b>Quiz Bot</b> — guruhlar uchun interaktiv test!\n\n"
            f"<b>Buyruqlar:</b>\n"
            f"/quiz_list — testlar ro'yxati\n"
            f"/quiz_start &lt;id&gt; — test boshlash\n"
            f"/quiz_stop — testni to'xtatish\n"
            f"/leaderboard — umumiy reyting\n"
            f"/my_score — mening natijalarim\n"
            f"/quiz_history — o'tgan testlar"
        )
    else:
        text = (
            f"👋 Salom! Admin <code>/quiz_start &lt;id&gt;</code> "
            f"bilan test boshlaydi."
        )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message, quiz_service: QuizService):
    await cmd_start(message, quiz_service)


# ══════════════════════════════════════════════════════
# /quiz_list
# ══════════════════════════════════════════════════════

@router.message(Command("quiz_list"))
async def cmd_quiz_list(message: Message, quiz_service: QuizService):
    quizzes = quiz_service.list_quizzes()
    if not quizzes:
        await message.answer(
            "📭 Hali test mavjud emas.\n"
            "Admin panelda test yarating!",
            parse_mode="HTML"
        )
        return

    lines = ["📚 <b>Mavjud testlar:</b>\n"]
    for q in quizzes:
        qid   = q.get("id", "?")
        title = q.get("title", "Nomsiz")
        count = q.get("question_count", len(q.get("questions", [])))
        tpq   = q.get("time_per_question", 30)
        desc  = q.get("description", "")
        lines.append(f"🔹 <b>{title}</b>")
        if desc:
            lines.append(f"   <i>{desc[:60]}</i>")
        lines.append(f"   📝 {count} ta savol  ·  ⏱ {tpq}s/savol")
        lines.append(f"   ID: <code>{qid}</code>\n")

    lines.append("▶️ Boshlash: <code>/quiz_start &lt;ID&gt;</code>")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ══════════════════════════════════════════════════════
# /quiz_start
# ══════════════════════════════════════════════════════

@router.message(Command("quiz_start"))
async def cmd_quiz_start(message: Message, bot: Bot,
                          quiz_service: QuizService,
                          group_manager: GroupManager):
    if message.chat.type == "private":
        await message.answer(
            "❌ Bu buyruq faqat guruhda ishlaydi!\n"
            "Meni guruhga qo'shing va u yerda ishlatng.",
            parse_mode="HTML"
        )
        return

    group_id = message.chat.id

    if session_manager.has_active_session(group_id):
        await message.answer(
            "⚠️ Guruhda test allaqachon ketmoqda!\n"
            "Avval <code>/quiz_stop</code> bilan to'xtating.",
            parse_mode="HTML"
        )
        return

    # Admin tekshiruvi
    is_admin = await group_manager.is_admin(message.chat.id, message.from_user.id)
    if not is_admin:
        await message.answer("❌ Faqat guruh adminlari test boshlashi mumkin.")
        return

    # Quiz ID
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "❌ Quiz ID kiriting:\n<code>/quiz_start &lt;quiz_id&gt;</code>",
            parse_mode="HTML"
        )
        return

    quiz_id = args[1].strip()
    quiz    = quiz_service.get_quiz_with_questions(quiz_id)
    if not quiz:
        await message.answer(
            f"❌ Test topilmadi: <code>{quiz_id}</code>\n"
            f"/quiz_list — mavjud testlar",
            parse_mode="HTML"
        )
        return

    questions = quiz.get("question_list") or quiz.get("questions", [])
    if not questions:
        await message.answer("❌ Testda savollar yo'q!", parse_mode="HTML")
        return

    time_per_q = quiz.get("time_per_question", 30)

    # Sessiya yaratish
    session = session_manager.create_session(
        quiz_id=quiz_id,
        quiz_title=quiz["title"],
        group_id=group_id,
        group_title=message.chat.title or "Guruh",
        started_by=message.from_user.id,
        questions=questions,
        time_per_question=time_per_q,
    )
    quiz_service.record_session_start(
        session_id=session.session_id,
        quiz_id=quiz_id,
        quiz_title=quiz["title"],
        group_id=group_id,
        group_title=message.chat.title or "Guruh",
        started_by=message.from_user.id,
    )

    await message.answer(
        f"🎯 <b>{quiz['title']}</b> boshlanmoqda!\n"
        f"📝 {len(questions)} ta savol  ·  ⏱ {time_per_q}s/savol\n\n"
        f"Tayyor bo'ling! 3...",
        parse_mode="HTML"
    )
    await asyncio.sleep(3)
    await _send_poll_question(bot, session, quiz_service)


# ══════════════════════════════════════════════════════
# POLL YUBORISH
# ══════════════════════════════════════════════════════

async def _send_poll_question(bot: Bot, session: QuizSession,
                               quiz_service: QuizService):
    """Joriy savolni Telegram Quiz Poll sifatida yuboradi."""
    q = session.current_question
    if not q:
        await _end_quiz(bot, session, quiz_service)
        return

    idx     = session.current_question_index
    total   = session.total_questions
    timeout = q.get("time_override", session.time_per_question)
    # Telegram open_period: 5–600 soniya
    timeout = max(5, min(600, timeout))

    options     = q.get("options", [])
    correct_idx = q.get("correct_index", 0)
    explanation = q.get("explanation", "").strip() or None

    # Savol matni
    question_text = f"❓ {idx+1}/{total}  {q['text']}"
    # Telegram poll savol matni max 300 belgi
    if len(question_text) > 300:
        question_text = question_text[:297] + "..."

    # Variantlar max 100 belgi
    clean_options = [str(o)[:100] for o in options[:4]]
    # Explanation max 200 belgi
    if explanation and len(explanation) > 200:
        explanation = explanation[:197] + "..."

    try:
        msg = await bot.send_poll(
            chat_id=session.group_id,
            question=question_text,
            options=clean_options,
            type="quiz",
            correct_option_id=correct_idx,
            explanation=explanation,
            explanation_parse_mode="HTML",
            is_anonymous=False,
            open_period=timeout,
        )
        session.current_poll_id      = msg.poll.id
        session.current_poll_msg_id  = msg.message_id
        session_manager.register_poll(msg.poll.id, session.group_id)

        # open_period tugagach keyingi savolga o'tamiz
        session._timer_task = asyncio.create_task(
            _wait_and_next(bot, session, quiz_service, timeout)
        )
        logger.info(
            f"Poll yuborildi: savol {idx+1}/{total} | "
            f"poll_id={msg.poll.id} | {timeout}s"
        )

    except TelegramAPIError as e:
        logger.error(f"Poll yuborishda xato: {e}")
        # Xato bo'lsa sessiyani to'xtatamiz
        session_manager.end_session(session.group_id)


async def _wait_and_next(bot: Bot, session: QuizSession,
                          quiz_service: QuizService, timeout: int):
    """open_period tugagach keyingi savolga o'tadi."""
    try:
        await asyncio.sleep(timeout + 1)  # +1s bufer

        if not session.is_active:
            return

        if session.is_last_question:
            session.advance_question()
            await asyncio.sleep(2)
            await _end_quiz(bot, session, quiz_service)
        else:
            session.advance_question()
            await asyncio.sleep(2)  # Oldingi poll yopilishini kutish
            await _send_poll_question(bot, session, quiz_service)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"_wait_and_next xatosi: {e}", exc_info=True)


# ══════════════════════════════════════════════════════
# POLL ANSWER — javoblarni qabul qilish
# ══════════════════════════════════════════════════════

@router.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer, quiz_service: QuizService):
    """
    Foydalanuvchi poll ga javob berganda chaqiriladi.
    is_anonymous=False bo'lgani uchun user ma'lumotlari keladi.
    """
    poll_id    = poll_answer.poll_id
    user       = poll_answer.user
    option_ids = poll_answer.option_ids  # Bo'sh = bekor qildi

    session = session_manager.get_session_by_poll(poll_id)
    if not session:
        return

    is_correct = session.record_poll_answer(
        user_id    = user.id,
        username   = user.username or "",
        first_name = user.first_name or "O'quvchi",
        option_ids = option_ids,
    )

    if is_correct is None:
        return  # Allaqachon javob bergan yoki bekor qildi

    # Foydalanuvchini ro'yxatdan o'tkazish
    quiz_service.register_user(user.id, user.first_name or "", user.username or "")


# ══════════════════════════════════════════════════════
# TEST YAKUNLASH
# ══════════════════════════════════════════════════════

async def _end_quiz(bot: Bot, session: QuizSession, quiz_service: QuizService):
    """Testni yakunlaydi va final leaderboard chiqaradi."""
    group_id      = session.group_id
    final_results = session.get_final_results()

    session_manager.end_session(group_id)

    await quiz_service.record_session_results(
        session_id=session.session_id,
        quiz_id=session.quiz_id,
        group_id=group_id,
        results=final_results,
    )

    lb_text = _format_final_leaderboard(final_results, session.quiz_title)

    for attempt in range(3):
        try:
            await bot.send_message(group_id, lb_text, parse_mode="HTML")
            break
        except TelegramAPIError as e:
            err = str(e).lower()
            if ("retry" in err or "flood" in err) and attempt < 2:
                import re
                m    = re.search(r'retry after (\d+)', err)
                wait = int(m.group(1)) + 1 if m else 15
                await asyncio.sleep(wait)
            else:
                logger.error(f"Leaderboard yuborishda xato: {e}")
                break


def _format_final_leaderboard(results: list, quiz_title: str,
                                stopped_early: bool = False) -> str:
    if not results:
        header = "⛔ Test to'xtatildi." if stopped_early else "🏁 Test yakunlandi!"
        return f"{header}\n\nHech kim javob bermadi."

    header = "⛔ <b>Test to'xtatildi!</b>" if stopped_early else "🏁 <b>Test yakunlandi!</b>"
    lines  = [
        header,
        f"📚 <b>{quiz_title}</b>",
        f"━━━━━━━━━━━━━━━━━━━━━\n",
        f"<b>🏆 Natijalar:</b>\n",
    ]

    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(results[:10]):
        name    = r.get("username") or r.get("first_name", "O'quvchi")
        score   = r.get("score", 0)
        correct = r.get("correct", 0)
        total   = r.get("total", 0)
        bar_n   = int(score / 10)
        bar     = "🟩" * bar_n + "⬜" * (10 - bar_n)
        medal   = medals[i] if i < 3 else f"  {i+1}."
        lines.append(
            f"{medal} <b>{name}</b>\n"
            f"    {bar}  {score:.0f}%  ({correct}/{total} ✅)\n"
        )

    if len(results) > 10:
        lines.append(f"<i>...va yana {len(results)-10} ishtirokchi</i>\n")

    avg = sum(r.get("score", 0) for r in results) / len(results)
    lines += [
        f"━━━━━━━━━━━━━━━━━━━━━",
        f"👥 Ishtirokchilar: <b>{len(results)} kishi</b>",
        f"📊 O'rtacha: <b>{avg:.1f}%</b>",
        f"\n🎉 Barcha ishtirokchilarga rahmat!",
    ]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════
# /quiz_stop
# ══════════════════════════════════════════════════════

@router.message(Command("quiz_stop"))
async def cmd_quiz_stop(message: Message, bot: Bot,
                         quiz_service: QuizService,
                         group_manager: GroupManager):
    group_id = message.chat.id
    session  = session_manager.get_session(group_id)

    if not session:
        await message.answer("⚠️ Hozir aktiv test yo'q.")
        return

    is_admin = await group_manager.is_admin(group_id, message.from_user.id)
    if not is_admin:
        await message.answer("❌ Faqat adminlar to'xtatishi mumkin.")
        return

    # Joriy pollni yopish
    if session.current_poll_msg_id:
        try:
            await bot.stop_poll(group_id, session.current_poll_msg_id)
        except TelegramAPIError:
            pass

    final_results = session.get_final_results()
    session_manager.end_session(group_id)

    await quiz_service.record_session_results(
        session_id=session.session_id,
        quiz_id=session.quiz_id,
        group_id=group_id,
        results=final_results,
    )

    lb_text = _format_final_leaderboard(final_results, session.quiz_title, stopped_early=True)
    await message.answer(lb_text, parse_mode="HTML")


# ══════════════════════════════════════════════════════
# /leaderboard
# ══════════════════════════════════════════════════════

@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message, quiz_service: QuizService):
    lb = LeaderboardService().get_global_leaderboard()
    if not lb:
        await message.answer("📊 Hali hech kim test yechmagan.", parse_mode="HTML")
        return

    lines  = ["🌍 <b>Umumiy Reyting</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(lb[:10]):
        name  = u.get("username") or u.get("first_name", "?")
        avg   = u.get("avg_score", 0)
        total = u.get("total_quizzes", 0)
        medal = medals[i] if i < 3 else f"  {i+1}."
        lines.append(f"{medal} <b>{name}</b>  —  {avg:.0f}%  <i>({total} test)</i>")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ══════════════════════════════════════════════════════
# /my_score
# ══════════════════════════════════════════════════════

@router.message(Command("my_score"))
async def cmd_my_score(message: Message, quiz_service: QuizService):
    user_id    = message.from_user.id
    first_name = message.from_user.first_name or "O'quvchi"
    history    = quiz_service.get_user_history(user_id)

    if not history:
        await message.answer(
            f"📊 <b>{first_name}</b>, hali hech qanday test yechmadingiz!\n\n"
            f"Guruhda test boshlanishini kuting.",
            parse_mode="HTML"
        )
        return

    total_correct   = sum(s.get("correct", 0) for s in history)
    total_questions = sum(s.get("total", 0) for s in history)
    avg_score       = sum(s.get("score", 0) for s in history) / len(history)

    lines = [
        f"📊 <b>{first_name} — Natijalarim</b>\n",
        f"🎯 O'tilgan testlar: <b>{len(history)}</b>",
        f"✅ To'g'ri: <b>{total_correct}/{total_questions}</b>",
        f"📈 O'rtacha: <b>{avg_score:.1f}%</b>\n",
        f"<b>So'nggi 5 ta:</b>",
    ]
    for s in history[-5:][::-1]:
        score   = s.get("score", 0)
        correct = s.get("correct", 0)
        total   = s.get("total", 0)
        title   = s.get("quiz_title", "?")[:30]
        icon    = "✅" if score >= 60 else "❌"
        lines.append(f"{icon}  <b>{title}</b>  —  {score:.0f}%  ({correct}/{total})")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ══════════════════════════════════════════════════════
# /quiz_history
# ══════════════════════════════════════════════════════

@router.message(Command("quiz_history"))
async def cmd_quiz_history(message: Message, quiz_service: QuizService):
    sessions = quiz_service.get_sessions()
    if not sessions:
        await message.answer("📭 Hali hech qanday test bo'lmagan.", parse_mode="HTML")
        return

    lines = ["📋 <b>So'nggi sessiyalar:</b>\n"]
    for s in list(reversed(sessions))[:10]:
        title   = s.get("quiz_title", "?")
        group   = s.get("group_title", "?")
        started = s.get("started_at", "")[:10]
        lines.append(f"📌 <b>{title}</b>")
        lines.append(f"   👥 {group}  ·  📅 {started}\n")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ══════════════════════════════════════════════════════
# TEST YARATISH — MATN YOKI JSON FAYL
# ══════════════════════════════════════════════════════

@router.message(Command("create_quiz"))
async def cmd_create_quiz(message: Message):
    await message.answer(
        "📝 <b>Test yaratish</b>\n\n"
        "<b>Usul 1 — Matn:</b>\n"
        "<code>Test nomi: Geografiya\n"
        "Vaqt: 30\n\n"
        "1. O'zbekiston poytaxti?\n"
        "A) Xiva\n"
        "B) Namangan\n"
        "*C) Toshkent\n"
        "D) Andijon\n"
        "Izoh: Toshkent 1930-yildan poytaxt\n\n"
        "2. ...</code>\n\n"
        "<b>Usul 2 — JSON fayl:</b> .json fayl yuboring\n\n"
        "⚠️ Izoh har savol ostiga yoziladi",
        parse_mode="HTML"
    )


@router.message(F.document)
async def handle_document(message: Message, bot: Bot, quiz_service: QuizService):
    if not await _is_admin_private(message, quiz_service):
        return

    doc = message.document
    if not doc.file_name.endswith(".json"):
        await message.answer("❌ Faqat .json fayl qabul qilinadi.")
        return

    wait_msg = await message.answer("⏳ Fayl o'qilmoqda...")
    try:
        file     = await bot.get_file(doc.file_id)
        bio      = await bot.download_file(file.file_path)
        raw_text = bio.read().decode("utf-8")
        import json
        data = json.loads(raw_text)
        await _save_quiz_from_data(data, message, wait_msg, quiz_service)
    except Exception as e:
        await wait_msg.edit_text(f"❌ Fayl o'qishda xato: {e}", parse_mode="HTML")


@router.message(F.text & F.text.startswith("Test nomi:"))
async def handle_text_quiz(message: Message, quiz_service: QuizService):
    if not await _is_admin_private(message, quiz_service):
        return

    wait_msg = await message.answer("⏳ Savollar o'qilmoqda...")
    try:
        data = _parse_text_quiz(message.text)
        await _save_quiz_from_data(data, message, wait_msg, quiz_service)
    except Exception as e:
        await wait_msg.edit_text(f"❌ Parse xatosi: {e}", parse_mode="HTML")


async def _is_admin_private(message: Message, quiz_service: QuizService) -> bool:
    """Faqat private chatda admin tekshiruvi."""
    if message.chat.type != "private":
        return False
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("❌ Faqat adminlar test yarata oladi.")
        return False
    return True


def _parse_text_quiz(text: str) -> dict:
    """Matn formatidan quiz data ni parse qiladi."""
    import re
    lines = text.strip().splitlines()
    title = ""
    description = ""
    time_per_q  = 30
    questions   = []

    i = 0
    # Header
    while i < len(lines):
        line = lines[i].strip()
        if line.lower().startswith("test nomi:"):
            title = line.split(":", 1)[1].strip()
        elif line.lower().startswith("tavsif:") or line.lower().startswith("description:"):
            description = line.split(":", 1)[1].strip()
        elif line.lower().startswith("vaqt:") or line.lower().startswith("time:"):
            try:
                time_per_q = int(re.search(r'\d+', line).group())
            except:
                pass
        elif re.match(r'^\d+[.)]\s', line):
            break
        i += 1

    # Savollar
    current_q = None
    for line in lines[i:]:
        line = line.strip()
        if not line:
            continue

        # Yangi savol
        m = re.match(r'^(\d+)[.)]\s*(?:\[(\d+)s?\])?\s*(.+)', line)
        if m:
            if current_q:
                questions.append(current_q)
            t_override = int(m.group(2)) if m.group(2) else None
            current_q = {
                "text":          m.group(3).strip(),
                "options":       [],
                "correct_index": 0,
                "type":          "multiple_choice",
                "explanation":   "",
            }
            if t_override:
                current_q["time_override"] = t_override
            continue

        # Izoh
        if line.lower().startswith("izoh:") or line.lower().startswith("explanation:"):
            if current_q:
                current_q["explanation"] = line.split(":", 1)[1].strip()
            continue

        # Variant
        m = re.match(r'^([*+]?)([A-Da-d])[.)]\s*([*+]?)(.+)', line)
        if m and current_q is not None:
            is_correct = bool(m.group(1) or m.group(3))
            opt_text   = m.group(4).strip()
            if opt_text.startswith("*") or opt_text.startswith("+"):
                is_correct = True
                opt_text   = opt_text[1:].strip()
            idx = len(current_q["options"])
            current_q["options"].append(opt_text)
            if is_correct:
                current_q["correct_index"] = idx

    if current_q:
        questions.append(current_q)

    return {
        "title":             title or "Nomsiz test",
        "description":       description,
        "time_per_question": time_per_q,
        "questions":         questions,
    }


async def _save_quiz_from_data(data: dict, message: Message,
                                wait_msg, quiz_service: QuizService):
    title     = data.get("title", "").strip()
    questions = data.get("questions", [])

    if not title:
        await wait_msg.edit_text("❌ Test nomi topilmadi!", parse_mode="HTML")
        return
    if not questions:
        await wait_msg.edit_text("❌ Savollar topilmadi!", parse_mode="HTML")
        return

    # Telegram poll cheklovi: max 10 variant, max 300 belgi savol
    for q in questions:
        q["options"] = q.get("options", [])[:10]

    time_per_q  = max(5, min(600, int(data.get("time_per_question", 30))))
    description = data.get("description", "")
    created_by  = message.from_user.username or message.from_user.first_name or "admin"

    no_correct = [i+1 for i, q in enumerate(questions)
                  if q.get("correct_index", -1) == -1 or not q.get("options")]

    try:
        quiz_id, ok = await quiz_service.create_quiz(
            title=title, description=description,
            created_by=created_by, questions=questions,
            time_per_question=time_per_q,
        )

        warn = ""
        if no_correct:
            nums = ", ".join(str(n) for n in no_correct[:5])
            warn = f"\n\n⚠️ {len(no_correct)} ta savolda to'g'ri javob yo'q ({nums})"

        bot_me       = await message.bot.get_me()
        bot_username = bot_me.username

        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="▶️ Guruhga qo'shish",
                url=f"https://t.me/{bot_username}?startgroup=start"
            ),
            InlineKeyboardButton(
                text="📤 Ulashish",
                url=f"https://t.me/share/url?url=https://t.me/{bot_username}&text=%2Fquiz_start%20{quiz_id}"
            ),
        ]])

        await wait_msg.edit_text(
            f"✅ <b>Test saqlandi!</b>\n\n"
            f"📚 <b>{title}</b>\n"
            f"🆔 <code>{quiz_id}</code>\n"
            f"❓ {len(questions)} ta savol  ·  ⏱ {time_per_q}s\n"
            f"👤 {created_by}"
            f"{warn}\n\n"
            f"<code>/quiz_start {quiz_id}</code>",
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error(f"Quiz saqlashda xato: {e}", exc_info=True)
        await wait_msg.edit_text(f"❌ Xato: <code>{e}</code>", parse_mode="HTML")

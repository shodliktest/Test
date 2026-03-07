"""
Bot Handlers - Guruh ommaviy test uchun to'liq handler
✅ Inline tugmalar orqali javob
✅ Countdown timer (real vaqt)
✅ Anti-cheat (bir marta javob, kech javob rad)
✅ To'g'ri javob ko'rsatish
✅ Final leaderboard
✅ Guruh admini tekshiruvi
"""
import asyncio
import logging
from typing import Optional

from aiogram import Bot, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.exceptions import TelegramAPIError

from bot.quiz_engine import session_manager, QuizSession
from bot.group_manager import GroupManager
from bot.leaderboard import LeaderboardService
from services.quiz_service import QuizService
from utils.config import config
from utils.helpers import get_rank_emoji

logger = logging.getLogger(__name__)

router = Router()


# ══════════════════════════════════════════════════════
# KLAVIATURA QURUVCHILAR
# ══════════════════════════════════════════════════════

def build_answer_keyboard(session_id: str, q_index: int, options: list) -> InlineKeyboardMarkup:
    """Ko'p tanlovli savol uchun inline klaviatura."""
    labels = ["🅐", "🅑", "🅒", "🅓"]
    buttons = []
    for i, opt in enumerate(options[:4]):
        label = labels[i] if i < len(labels) else str(i + 1)
        buttons.append([InlineKeyboardButton(
            text=f"{label}  {opt[:45]}",
            callback_data=f"ans:{session_id}:{q_index}:{i}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_true_false_keyboard(session_id: str, q_index: int) -> InlineKeyboardMarkup:
    """Ha/Yo'q savol uchun klaviatura."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅  Ha / True",  callback_data=f"ans:{session_id}:{q_index}:0"),
        InlineKeyboardButton(text="❌  Yo'q / False", callback_data=f"ans:{session_id}:{q_index}:1"),
    ]])


def build_countdown_bar(seconds_left: int, total: int) -> str:
    """Progress bar sifatida countdown ko'rsatish."""
    filled = int((seconds_left / total) * 10)
    bar = "🟩" * filled + "⬜" * (10 - filled)
    return f"{bar}  {seconds_left}s"


# ══════════════════════════════════════════════════════
# /start  va  /help
# ══════════════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message):
    name = message.from_user.first_name or "o'quvchi"
    chat_type = message.chat.type

    if chat_type == "private":
        text = (
            f"👋 Salom, <b>{name}</b>!\n\n"
            f"Men <b>Quiz Bot</b> — guruhlar uchun interaktiv test platformasi!\n\n"
            f"<b>📌 Qanday ishlaydi?</b>\n"
            f"1. Meni guruhga qo'shing\n"
            f"2. Guruhda admin bo'ling\n"
            f"3. <code>/quiz_list</code> — testlar ro'yxati\n"
            f"4. <code>/quiz_start &lt;id&gt;</code> — testni boshlang\n"
            f"5. O'quvchilar tugmalar orqali javob beradi\n\n"
            f"<b>🛠 Barcha buyruqlar:</b>\n"
            f"/quiz_list — Mavjud testlar\n"
            f"/quiz_start &lt;id&gt; — Test boshlash (admin)\n"
            f"/quiz_stop — Testni to'xtatish (admin)\n"
            f"/leaderboard — Umumiy reyting\n"
            f"/my_score — Mening natijalarim\n"
            f"/quiz_history — O'tgan testlar\n"
            f"/help — Yordam"
        )
    else:
        text = (
            f"👋 Salom! Men <b>Quiz Bot</b>.\n"
            f"Admin <code>/quiz_start &lt;id&gt;</code> buyrug'i bilan test boshlaydi.\n"
            f"O'quvchilar tugmalar orqali javob beradi!"
        )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    await cmd_start(message)


# ══════════════════════════════════════════════════════
# /quiz_list
# ══════════════════════════════════════════════════════

@router.message(Command("quiz_list"))
async def cmd_quiz_list(message: Message, quiz_service: QuizService):
    quizzes = await quiz_service.list_quizzes()
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
        count = q.get("questions", 0)
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
# /quiz_start — GURUHDA TEST BOSHLASH
# ══════════════════════════════════════════════════════

@router.message(Command("quiz_start"))
async def cmd_quiz_start(message: Message, bot: Bot,
                          quiz_service: QuizService,
                          group_manager: GroupManager):
    group_id = message.chat.id
    user_id  = message.from_user.id

    # Faqat guruhlarda ishlaydi
    if message.chat.type == "private":
        await message.answer(
            "❌ Bu buyruq faqat guruhlarda ishlaydi!\n\n"
            "1. Meni guruhga qo'shing\n"
            "2. Admin huquqi bering\n"
            "3. Guruhda /quiz_start buyrug'ini yozing",
            parse_mode="HTML"
        )
        return

    # Admin tekshiruvi
    if not await group_manager.is_group_admin(group_id, user_id):
        await message.answer(
            "❌ Faqat guruh <b>adminlari</b> test boshlay oladi!\n"
            "Avval admin huquqini oling.",
            parse_mode="HTML"
        )
        return

    # Quiz ID ni ajratish
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "❌ <b>Foydalanish:</b> <code>/quiz_start &lt;quiz_id&gt;</code>\n\n"
            "Mavjud testlarni ko'rish: /quiz_list",
            parse_mode="HTML"
        )
        return

    quiz_id = args[1].strip()

    # Faol sessiya bormi?
    if session_manager.has_active_session(group_id):
        await message.answer(
            "⚠️ Bu guruhda test allaqachon ketmoqda!\n"
            "Avval to'xtatish: /quiz_stop",
            parse_mode="HTML"
        )
        return

    # Testni yuklash
    quiz = await quiz_service.get_quiz_with_questions(quiz_id)
    if not quiz:
        await message.answer(
            f"❌ <code>{quiz_id}</code> ID li test topilmadi.\n"
            f"Ro'yxatni ko'ring: /quiz_list",
            parse_mode="HTML"
        )
        return

    questions = quiz.get("question_list", [])
    if not questions:
        await message.answer("❌ Bu testda savollar yo'q!", parse_mode="HTML")
        return

    # Sessiya yaratish
    group_title = message.chat.title or "Guruh"
    session = session_manager.create_session(
        quiz_id=quiz_id,
        quiz_title=quiz["title"],
        group_id=group_id,
        group_title=group_title,
        started_by=user_id,
        questions=questions,
        time_per_question=quiz.get("time_per_question", config.DEFAULT_QUESTION_TIMEOUT)
    )

    # DB ga yozish
    await quiz_service.record_session_start(
        session_id=session.session_id,
        quiz_id=quiz_id,
        quiz_title=quiz["title"],
        group_id=group_id,
        group_title=group_title,
        started_by=user_id
    )

    # Boshlash e'loni
    starter_name = message.from_user.first_name or "Admin"
    await message.answer(
        f"🎯 <b>{quiz['title']}</b> testi boshlanmoqda!\n\n"
        f"👤 Boshlovchi: {starter_name}\n"
        f"📝 Savollar soni: <b>{len(questions)} ta</b>\n"
        f"⏱ Har savol uchun: <b>{quiz.get('time_per_question', 30)} soniya</b>\n\n"
        f"👇 Har bir savolga tugmalar orqali javob bering!\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ <b>3 soniyadan keyin boshlanadi...</b>",
        parse_mode="HTML"
    )

    await asyncio.sleep(3)
    await _send_next_question(bot, session, quiz_service)


# ══════════════════════════════════════════════════════
# /quiz_stop
# ══════════════════════════════════════════════════════

@router.message(Command("quiz_stop"))
async def cmd_quiz_stop(message: Message, bot: Bot,
                         quiz_service: QuizService,
                         group_manager: GroupManager,
                         leaderboard_service: LeaderboardService):
    group_id = message.chat.id
    user_id  = message.from_user.id

    if not await group_manager.is_group_admin(group_id, user_id):
        await message.answer("❌ Faqat <b>adminlar</b> testni to'xtatishi mumkin!", parse_mode="HTML")
        return

    session = session_manager.get_session(group_id)
    if not session:
        await message.answer("ℹ️ Bu guruhda faol test yo'q.", parse_mode="HTML")
        return

    session.cancel_timer()
    final_results = session.get_final_results()
    session_manager.end_session(group_id)

    await quiz_service.record_session_results(
        session_id=session.session_id,
        quiz_id=session.quiz_id,
        group_id=group_id,
        results=final_results
    )

    lb = _format_final_leaderboard(final_results, session.quiz_title, stopped_early=True)
    await message.answer(lb, parse_mode="HTML")


# ══════════════════════════════════════════════════════
# /leaderboard
# ══════════════════════════════════════════════════════

@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message, leaderboard_service: LeaderboardService):
    global_lb = await leaderboard_service.get_global_leaderboard()
    if not global_lb:
        await message.answer("📊 Hali hech kim test yechmagan.", parse_mode="HTML")
        return

    lines = ["🌍 <b>Umumiy Reyting (Global)</b>\n"]
    emojis = ["🥇","🥈","🥉"] + [f"{i}." for i in range(4, 11)]
    for i, u in enumerate(global_lb[:10]):
        name  = u.get("username") or u.get("first_name","?")
        avg   = u.get("avg_score", 0)
        total = u.get("total_quizzes", 0)
        lines.append(f"{emojis[i]}  <b>{name}</b>  —  {avg:.0f}%  <i>({total} test)</i>")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ══════════════════════════════════════════════════════
# /my_score
# ══════════════════════════════════════════════════════

@router.message(Command("my_score"))
async def cmd_my_score(message: Message, leaderboard_service: LeaderboardService):
    user_id    = message.from_user.id
    first_name = message.from_user.first_name or "O'quvchi"

    all_scores  = leaderboard_service.db.get_all_scores_from_cache()
    user_scores = [s for s in all_scores if s.get("user_id") == user_id]

    if not user_scores:
        await message.answer(
            f"📊 <b>{first_name}</b>, siz hali hech qanday test yechmagansiz!\n\n"
            f"Guruhda /quiz_start bilan test boshlanishini kuting.",
            parse_mode="HTML"
        )
        return

    total_correct   = sum(s.get("correct", 0) for s in user_scores)
    total_questions = sum(s.get("total", 0) for s in user_scores)
    avg_score       = sum(s.get("score", 0) for s in user_scores) / len(user_scores)

    lines = [
        f"📊 <b>{first_name} — Natijalarim</b>\n",
        f"🎯 O'tilgan testlar: <b>{len(user_scores)}</b>",
        f"✅ To'g'ri javoblar: <b>{total_correct}/{total_questions}</b>",
        f"📈 O'rtacha ball: <b>{avg_score:.1f}%</b>\n",
        f"<b>So'nggi 5 urinish:</b>",
    ]
    for s in user_scores[-5:][::-1]:
        score   = s.get("score", 0)
        correct = s.get("correct", 0)
        total   = s.get("total", 0)
        qid     = s.get("quiz_id","?")[-12:]
        icon    = "✅" if score >= 60 else "❌"
        lines.append(f"{icon}  <code>{qid}</code>  —  {score:.0f}%  ({correct}/{total})")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ══════════════════════════════════════════════════════
# /quiz_history
# ══════════════════════════════════════════════════════

@router.message(Command("quiz_history"))
async def cmd_quiz_history(message: Message, quiz_service: QuizService):
    sessions = quiz_service.db.get_sessions_from_cache()
    if not sessions:
        await message.answer("📭 Hali hech qanday test sessiyasi bo'lmagan.", parse_mode="HTML")
        return

    lines = ["📋 <b>So'nggi test sessiyalari:</b>\n"]
    for s in reversed(sessions[-10:]):
        title   = s.get("quiz_title","?")
        group   = s.get("group_title","?")
        started = s.get("started_at","")[:10]
        lines.append(f"📌 <b>{title}</b>")
        lines.append(f"   👥 {group}  ·  📅 {started}\n")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ══════════════════════════════════════════════════════
# JAVOB TUGMASI BOSILGANDA (CALLBACK)
# ══════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("ans:"))
async def handle_answer(callback: CallbackQuery):
    """Foydalanuvchi javob tugmasini bosganida ishlaydigan handler."""
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("❌ Noto'g'ri format.", show_alert=False)
        return

    _, session_id, q_index_str, answer_index_str = parts
    q_index      = int(q_index_str)
    answer_index = int(answer_index_str)
    user         = callback.from_user
    group_id     = callback.message.chat.id

    # ── Sessiya tekshiruvi ──
    session = session_manager.get_session(group_id)
    if not session:
        await callback.answer("❌ Faol test sessiyasi topilmadi.", show_alert=False)
        return

    # ── Sessiya ID tekshiruvi (boshqa sessiyadan eski tugma) ──
    if session.session_id != session_id:
        await callback.answer("🔄 Bu savol boshqa sessiyaga tegishli.", show_alert=False)
        return

    # ── Savol indeksi tekshiruvi (anti-cheat: kech javob) ──
    if q_index != session.current_question_index:
        await callback.answer("⏰ Kechikdingiz! Bu savol o'tib ketdi.", show_alert=True)
        return

    # ── Javob qabul qilish ──
    result = session.record_answer(
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "O'quvchi",
        answer_index=answer_index
    )

    # ── Natijani bildirish ──
    if result is None:
        if session.answers_locked:
            await callback.answer("🔒 Vaqt tugadi! Javoblar qabul qilinmayapti.", show_alert=True)
        else:
            await callback.answer("✋ Siz allaqachon javob bergansiz!", show_alert=False)
        return

    if result:
        # To'g'ri javob — faqat shu foydalanuvchiga ko'rinadi
        await callback.answer("✅ To'g'ri! Ajoyib!", show_alert=False)
    else:
        # Noto'g'ri — to'g'ri javobni ko'rsat
        q           = session.current_question
        correct_i   = q.get("correct_index", 0)
        options     = q.get("options", [])
        correct_ans = options[correct_i] if correct_i < len(options) else "?"
        await callback.answer(
            f"❌ Noto'g'ri!\n✅ To'g'ri javob: {correct_ans}",
            show_alert=True
        )


# ══════════════════════════════════════════════════════
# ASOSIY QUIZ OQIMI — GURUH UCHUN
# ══════════════════════════════════════════════════════

async def _send_next_question(bot: Bot, session: QuizSession, quiz_service: QuizService):
    """Navbatdagi savolni guruhga yuborish."""
    q = session.current_question
    if not q:
        await _end_quiz(bot, session, quiz_service)
        return

    group_id = session.group_id
    idx      = session.current_question_index
    total    = session.total_questions
    q_type   = q.get("question_type", "multiple_choice")
    options  = q.get("options", [])

    # ── Savol matni ──
    opt_labels = ["🅐", "🅑", "🅒", "🅓"]
    if q_type == "multiple_choice" and options:
        opts_text = "\n".join(
            f"  {opt_labels[i]}  {opt}"
            for i, opt in enumerate(options[:4])
        )
        question_body = (
            f"❓ <b>Savol {idx+1}/{total}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"{q['text']}\n\n"
            f"{opts_text}\n\n"
            f"⏱ <b>{session.time_per_question} soniya</b>"
        )
        kb = build_answer_keyboard(session.session_id, idx, options)

    elif q_type == "true_false":
        question_body = (
            f"❓ <b>Savol {idx+1}/{total}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"{q['text']}\n\n"
            f"⏱ <b>{session.time_per_question} soniya</b>"
        )
        kb = build_true_false_keyboard(session.session_id, idx)

    else:  # fill_in_blank yoki boshqa
        question_body = (
            f"❓ <b>Savol {idx+1}/{total}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"{q['text']}\n\n"
            f"⏱ <b>{session.time_per_question} soniya</b>"
        )
        kb = build_answer_keyboard(session.session_id, idx, options)

    # Rasm bormi?
    image_url = q.get("image_url", "")

    try:
        session.is_question_active = True
        session.answers_locked     = False

        if image_url:
            try:
                msg = await bot.send_photo(
                    group_id,
                    photo=image_url,
                    caption=question_body,
                    parse_mode="HTML",
                    reply_markup=kb
                )
            except TelegramAPIError:
                msg = await bot.send_message(group_id, question_body,
                                              parse_mode="HTML", reply_markup=kb)
        else:
            msg = await bot.send_message(group_id, question_body,
                                          parse_mode="HTML", reply_markup=kb)

        session.question_message_id = msg.message_id

        # Timer ishga tushirish
        session._timer_task = asyncio.create_task(
            _question_timer(bot, session, quiz_service)
        )

    except TelegramAPIError as e:
        logger.error(f"Savol yuborishda xato: {e}")


async def _question_timer(bot: Bot, session: QuizSession, quiz_service: QuizService):
    """Savol vaqtini boshqarish — countdown va to'g'ri javobni ko'rsatish."""
    try:
        time_total = session.time_per_question

        # ── Countdown xabarlari (10s, 5s, 3s, 2s, 1s) ──
        checkpoints = []
        if time_total >= 15:
            checkpoints.append((time_total - 10, 10))
        if time_total >= 8:
            checkpoints.append((time_total - 5,  5))
        for sec in [3, 2, 1]:
            if time_total > sec:
                checkpoints.append((time_total - sec, sec))

        elapsed = 0
        for wait, remaining in checkpoints:
            to_wait = wait - elapsed
            if to_wait > 0:
                await asyncio.sleep(to_wait)
                elapsed = wait
            if not session.is_active:
                return
            # ⏰ Reminder xabari (faqat 5s dan past)
            if remaining <= 5:
                try:
                    await bot.send_message(
                        session.group_id,
                        f"⏰ <b>{remaining} soniya qoldi!</b>",
                        parse_mode="HTML"
                    )
                except TelegramAPIError:
                    pass

        # Qolgan vaqtni kutish
        remaining_sleep = time_total - elapsed
        if remaining_sleep > 0:
            await asyncio.sleep(remaining_sleep)

        if not session.is_active:
            return

        # ── Javoblarni qulflash ──
        session.lock_answers()

        # ── To'g'ri javobni e'lon qilish ──
        q           = session.current_question
        if q:
            correct_i    = q.get("correct_index", 0)
            options      = q.get("options", [])
            correct_text = options[correct_i] if correct_i < len(options) else "?"
            explanation  = q.get("explanation", "")

            answered     = len(session.current_answers)
            correct_cnt  = sum(1 for a in session.current_answers.values() if a.is_correct)

            # Kimlar to'g'ri javob berganini ko'rsatish (max 5 kishi)
            correct_names = [
                a.first_name or a.username or "O'quvchi"
                for a in session.current_answers.values()
                if a.is_correct
            ][:5]

            reveal_lines = [
                f"⏰ <b>Vaqt tugadi!</b>",
                f"━━━━━━━━━━━━━━━━━━━━━",
                f"✅ <b>To'g'ri javob:</b>  {correct_text}",
                f"👥 Javob berdi: {answered} kishi  |  ✅ To'g'ri: {correct_cnt}",
            ]
            if correct_names:
                reveal_lines.append(f"🌟 To'g'ri: {', '.join(correct_names)}")
            if explanation:
                reveal_lines.append(f"\n💡 <i>{explanation}</i>")

            # Mini leaderboard (agar 3+ savol o'tilgan bo'lsa)
            if session.current_question_index >= 2:
                lb = session.get_leaderboard()[:3]
                if lb:
                    reveal_lines.append("\n<b>📊 Hozirgi holat:</b>")
                    emojis = ["🥇","🥈","🥉"]
                    for i, r in enumerate(lb):
                        name = r.get("username") or r.get("first_name","?")
                        reveal_lines.append(
                            f"{emojis[i]} {name} — {r.get('correct',0)}/{session.current_question_index+1}"
                        )

            try:
                await bot.send_message(
                    session.group_id,
                    "\n".join(reveal_lines),
                    parse_mode="HTML"
                )
            except TelegramAPIError:
                pass

        await asyncio.sleep(2)

        if not session.is_active:
            return

        # ── Keyingi savolga o'tish yoki tugatish ──
        if session.is_last_question:
            session.advance_question()
            await _end_quiz(bot, session, quiz_service)
        else:
            session.advance_question()
            await asyncio.sleep(1)  # Oz pauza
            await _send_next_question(bot, session, quiz_service)

    except asyncio.CancelledError:
        logger.info(f"Timer bekor qilindi: {session.session_id}")
    except Exception as e:
        logger.error(f"Timer xatosi: {e}", exc_info=True)


async def _end_quiz(bot: Bot, session: QuizSession, quiz_service: QuizService):
    """Testni yakunlash, natijalarni saqlash va final leaderboard ko'rsatish."""
    group_id      = session.group_id
    final_results = session.get_final_results()

    session_manager.end_session(group_id)

    # ── DB ga saqlash ──
    await quiz_service.record_session_results(
        session_id=session.session_id,
        quiz_id=session.quiz_id,
        group_id=group_id,
        results=final_results
    )

    # ── Final leaderboard ──
    lb_text = _format_final_leaderboard(final_results, session.quiz_title)
    try:
        await bot.send_message(group_id, lb_text, parse_mode="HTML")
    except TelegramAPIError as e:
        logger.error(f"Final leaderboard yuborishda xato: {e}")


def _format_final_leaderboard(results: list, quiz_title: str,
                                stopped_early: bool = False) -> str:
    """Final natijalar xabarini formatlash."""
    if not results:
        header = "⛔ Test to'xtatildi." if stopped_early else "🏁 Test yakunlandi!"
        return f"{header}\n\nHech kim javob bermadi."

    header = (
        f"⛔ <b>Test to'xtatildi!</b>\n" if stopped_early
        else f"🏁 <b>Test yakunlandi!</b>\n"
    )

    lines = [
        header,
        f"📚 <b>{quiz_title}</b>",
        f"━━━━━━━━━━━━━━━━━━━━━\n",
    ]

    emojis = ["🥇","🥈","🥉"] + [f"{i}." for i in range(4, 11)]
    for i, r in enumerate(results[:10]):
        name    = r.get("username") or r.get("first_name","O'quvchi")
        score   = r.get("score", 0)
        correct = r.get("correct", 0)
        total   = r.get("total", 0)
        bar     = "🟩" * int(score / 10) + "⬜" * (10 - int(score / 10))
        lines.append(
            f"{emojis[i]}  <b>{name}</b>\n"
            f"    {bar}  {score:.0f}%  ({correct}/{total} ✅)"
        )

    if len(results) > 10:
        lines.append(f"\n<i>...va yana {len(results)-10} ishtirokchi</i>")

    avg = sum(r.get("score",0) for r in results) / len(results)
    lines += [
        f"\n━━━━━━━━━━━━━━━━━━━━━",
        f"👥 Ishtirokchilar: <b>{len(results)}</b>",
        f"📊 O'rtacha ball: <b>{avg:.1f}%</b>",
        f"\n🎉 Barcha ishtirokchilarga rahmat!"
    ]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════
# TEST YARATISH — ODDIY MATN YOKI FAYL ORQALI
# ══════════════════════════════════════════════════════

import json as _json
import io as _io
import re as _re

# ── Namuna matn formati ──────────────────────────────
SAMPLE_TEXT = """Test nomi: Geografiya testi
Vaqt: 30

1. O'zbekiston poytaxti qayer?
A) Xiva
B) Namangan
*C) Toshkent
D) Andijon

2. Eng baland tog' qaysi?
A) Elbrус
*B) Everest
C) Kilimanjaro
D) Fuji

3. Kaspiy dengizi qaysi okean havzasiga kiradi?
+A) Hech qaysi (yopiq havza)
B) Atlantika
C) Tinch okean
D) Hind okeani"""


# ══════════════════════════════════════════════════════
# MATN FORMATI PARSER
# ══════════════════════════════════════════════════════

def parse_text_quiz(text: str) -> dict:
    """
    Oddiy matn formatdagi testni parse qiladi.

    Qo'llab-quvvatlanadigan formatlar:
      - To'g'ri javob: * yoki + bilan belgilanadi
        *A) Javob   yoki   A) *Javob   yoki   +A) Javob
      - Savol raqami: "1." yoki "1)" formatda
      - Sarlavha: "Test nomi: ..." yoki birinchi qator
      - Vaqt: "Vaqt: 30" yoki "Time: 30"
    """
    lines = [l.rstrip() for l in text.strip().splitlines()]

    title       = ""
    time_per_q  = 30
    description = ""
    questions   = []

    # ── Sarlavha va meta ma'lumotlar ──
    content_lines = []
    for line in lines:
        low = line.lower().strip()

        # Sarlavha
        if not title and _re.match(r'^(test nomi|title|nom)\s*:', low):
            title = _re.sub(r'^[^:]+:\s*', '', line, flags=_re.IGNORECASE).strip()
            continue

        # Vaqt
        if _re.match(r'^(vaqt|time|seconds?)\s*:', low):
            val = _re.sub(r'^[^:]+:\s*', '', line, flags=_re.IGNORECASE).strip()
            try:
                time_per_q = max(5, min(120, int(val)))
            except ValueError:
                pass
            continue

        # Tavsif
        if _re.match(r'^(tavsif|description|izoh)\s*:', low):
            description = _re.sub(r'^[^:]+:\s*', '', line, flags=_re.IGNORECASE).strip()
            continue

        content_lines.append(line)

    # ── Savollarni ajratish ──
    # Savol boshlanishini aniqlash: "1." "1)" "1-"
    Q_START = _re.compile(r'^\s*(\d+)\s*[.\-\)]\s+(.+)')
    # Variant boshlanishi: A) B) C) D)  (yoki *A) +B) A)* va h.k.)
    OPT_RE  = _re.compile(
        r'^\s*'
        r'(?P<correct1>[*+])?'          # * yoki + boshida
        r'\s*(?P<label>[A-Da-d])'       # A B C D
        r'\s*[.\-\)]\s*'               # ). yoki -
        r'(?P<correct2>[*+])?'          # * yoki + labeldan keyin
        r'\s*(?P<text>.+)'             # variant matni
    )

    current_q   = None
    current_opts = []
    correct_idx  = -1

    def flush_question():
        nonlocal current_q, current_opts, correct_idx
        if current_q and current_opts:
            if correct_idx == -1:
                correct_idx = 0  # Default: birinchi variant
            questions.append({
                "text":          current_q,
                "type":          "multiple_choice",
                "options":       [o for o in current_opts],
                "correct_index": correct_idx,
                "explanation":   "",
                "image_url":     "",
            })
        current_q    = None
        current_opts = []
        correct_idx  = -1

    for line in content_lines:
        if not line.strip():
            continue

        # Yangi savol?
        m_q = Q_START.match(line)
        if m_q:
            flush_question()
            current_q   = m_q.group(2).strip()
            current_opts = []
            correct_idx  = -1
            continue

        # Variant?
        m_o = OPT_RE.match(line)
        if m_o and current_q is not None:
            is_correct = bool(m_o.group("correct1") or m_o.group("correct2"))
            opt_text   = m_o.group("text").strip()

            # Variant matnida * yoki + bor?
            # masalan:  A) *Toshkent
            if opt_text.startswith(("*", "+")):
                is_correct = True
                opt_text   = opt_text[1:].strip()

            if is_correct:
                correct_idx = len(current_opts)

            current_opts.append(opt_text)
            continue

        # Savol davomi (ko'p qatorli savol)
        if current_q is not None and not m_o:
            current_q += " " + line.strip()

    flush_question()  # Oxirgi savolni saqlash

    # Sarlavha topilmagan bo'lsa — birinchi savoldan oldingi matn
    if not title:
        title = "Yangi Test"

    return {
        "title":            title,
        "description":      description,
        "time_per_question": time_per_q,
        "questions":        questions,
    }


# ══════════════════════════════════════════════════════
# /create_quiz — YO'RIQNOMA VA NAMUNA
# ══════════════════════════════════════════════════════

@router.message(Command("create_quiz"))
async def cmd_create_quiz(message: Message, bot: Bot):
    """
    /create_quiz — test yaratish yo'riqnomasi.
    Faqat adminlar uchun.
    """
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("❌ Bu buyruq faqat <b>adminlar</b> uchun!", parse_mode="HTML")
        return

    await message.answer(
        "📋 <b>Test yaratish — 2 usul:</b>\n\n"

        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📝 <b>1-usul: Matn yuborish</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Quyidagi formatda <b>to'g'ridan-to'g'ri xabar yozing</b>:\n\n"

        "<code>Test nomi: Geografiya\n"
        "Vaqt: 30\n\n"
        "1. Savol matni?\n"
        "A) Variant\n"
        "B) Variant\n"
        "*C) To'g'ri javob\n"
        "D) Variant\n\n"
        "2. Keyingi savol?\n"
        "+A) To'g'ri javob\n"
        "B) Variant\n"
        "C) Variant</code>\n\n"

        "✅ <b>To'g'ri javob belgisi:</b> <code>*</code> yoki <code>+</code>\n"
        "   Variantdan oldin: <code>*A)</code> yoki <code>+A)</code>\n"
        "   Variantdan keyin: <code>A) *Toshkent</code>\n\n"

        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📄 <b>2-usul: .txt yoki .json fayl</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Xuddi shu formatda fayl yaratib yuboring.\n\n"
        "👇 Namuna fayl:",
        parse_mode="HTML"
    )

    # Namuna .txt faylni yuborish
    from aiogram.types import BufferedInputFile
    sample_bytes = SAMPLE_TEXT.encode("utf-8")
    await bot.send_document(
        chat_id=message.chat.id,
        document=BufferedInputFile(sample_bytes, filename="namuna_test.txt"),
        caption=(
            "📥 Shu faylni yuklab, to'ldirib qayta yuboring!\n\n"
            "<b>Qoidalar:</b>\n"
            "• <code>*A)</code> yoki <code>+A)</code> — to'g'ri javob\n"
            "• Har bir savol raqam bilan boshlanadi: <code>1.</code> <code>2.</code>\n"
            "• Variantlar: <code>A)</code> <code>B)</code> <code>C)</code> <code>D)</code>\n"
            "• <code>Vaqt: 30</code> — soniya (5-120)\n"
            "• <code>Test nomi: ...</code> — sarlavha"
        ),
        parse_mode="HTML"
    )



# ══════════════════════════════════════════════════════
# FAYL QABUL QILISH (.txt yoki .json)
# ══════════════════════════════════════════════════════

@router.message(F.document)
async def handle_document(message: Message, bot: Bot, quiz_service: QuizService):
    """Admin yuborgan .txt yoki .json fayldan test yaratadi."""
    if message.from_user.id not in config.ADMIN_IDS:
        return

    doc   = message.document
    fname = (doc.file_name or "").lower()

    if not (fname.endswith(".txt") or fname.endswith(".json")):
        await message.answer(
            "⚠️ Faqat <b>.txt</b> yoki <b>.json</b> fayl qabul qilinadi!\n"
            "/create_quiz — namuna olish",
            parse_mode="HTML"
        )
        return

    if doc.file_size and doc.file_size > 500_000:
        await message.answer("❌ Fayl 500 KB dan kichik bo'lishi kerak!")
        return

    wait_msg = await message.answer("⏳ Fayl o'qilmoqda...")

    try:
        file       = await bot.get_file(doc.file_id)
        file_bytes = await bot.download_file(file.file_path)
        content    = file_bytes.read().decode("utf-8")
    except Exception as e:
        await wait_msg.edit_text(f"❌ Faylni yuklab bo'lmadi: {e}")
        return

    # .json yoki .txt parse qilish
    if fname.endswith(".json"):
        try:
            raw = _json.loads(content)
            # JSON formatda kelgan bo'lsa — to'g'ridan parse
            data = _parse_json_data(raw)
        except _json.JSONDecodeError as e:
            await wait_msg.edit_text(
                f"❌ <b>JSON xatosi:</b>\n<code>{str(e)[:200]}</code>",
                parse_mode="HTML"
            )
            return
    else:
        # .txt — oddiy matn format
        data = parse_text_quiz(content)

    await _save_quiz_from_data(data, message, wait_msg, quiz_service)


# ══════════════════════════════════════════════════════
# TO'G'RIDAN XABAR ORQALI TEST YARATISH
# ══════════════════════════════════════════════════════

@router.message(F.text & F.text.startswith("Test nomi:"))
async def handle_text_quiz(message: Message, quiz_service: QuizService):
    """
    Admin 'Test nomi:' bilan boshlanadigan xabar yuborganda
    to'g'ridan test yaratadi — fayl shart emas!
    """
    if message.from_user.id not in config.ADMIN_IDS:
        return

    wait_msg = await message.answer("⏳ Test o'qilmoqda...")
    data = parse_text_quiz(message.text)
    await _save_quiz_from_data(data, message, wait_msg, quiz_service)


# ══════════════════════════════════════════════════════
# YORDAMCHI FUNKSIYALAR
# ══════════════════════════════════════════════════════

def _parse_json_data(raw: dict) -> dict:
    """JSON dict ni ichki formatga o'giradi."""
    questions = []
    for q in raw.get("questions", []):
        questions.append({
            "text":          str(q.get("text", "")).strip(),
            "type":          q.get("type", "multiple_choice"),
            "options":       [str(o) for o in q.get("options", [])[:4]],
            "correct_index": int(q.get("correct_index", 0)),
            "explanation":   str(q.get("explanation", "")).strip(),
            "image_url":     str(q.get("image_url", "")).strip(),
        })
    return {
        "title":             raw.get("title", "Yangi Test").strip(),
        "description":       raw.get("description", "").strip(),
        "time_per_question": int(raw.get("time_per_question", 30)),
        "questions":         questions,
    }


def _format_for_cache(record: dict) -> str:
    """update_cache uchun DB_RECORD formatida matn."""
    import json as _j
    return f"📦 DB_RECORD\n```json\n{_j.dumps(record, ensure_ascii=False)}\n```"


async def _save_quiz_from_data(data: dict, message: Message,
                                wait_msg, quiz_service: QuizService):
    """Parse qilingan ma'lumotni tekshirib DB ga saqlaydi."""
    from utils.helpers import generate_id, build_quiz_record, build_question_record

    title     = data.get("title", "").strip()
    questions = data.get("questions", [])

    # ── Tekshirish ──
    if not title:
        await wait_msg.edit_text(
            "❌ <b>Test nomi topilmadi!</b>\n\n"
            "Matn birinchi qatordan boshlang:\n"
            "<code>Test nomi: Geografiya testi</code>",
            parse_mode="HTML"
        )
        return

    if not questions:
        await wait_msg.edit_text(
            "❌ <b>Savollar topilmadi!</b>\n\n"
            "Format to'g'riligini tekshiring:\n"
            "<code>1. Savol matni?\n"
            "A) Variant\n"
            "*B) To'g'ri javob</code>",
            parse_mode="HTML"
        )
        return

    # To'g'ri javobsiz savollarni aniqlash
    no_correct = [
        i + 1 for i, q in enumerate(questions)
        if q.get("correct_index", -1) == -1
    ]

    time_per_q  = max(5, min(120, int(data.get("time_per_question", 30))))
    description = data.get("description", "")
    created_by  = message.from_user.username or message.from_user.first_name or "admin"

    try:
        quiz_id  = generate_id("quiz")
        quiz_rec = build_quiz_record(
            quiz_id, title, description, created_by,
            len(questions), time_per_q
        )
        msg_id = await quiz_service.db.write_record(quiz_rec)
        if msg_id:
            quiz_service.db.update_cache(msg_id, _format_for_cache(quiz_rec))

        for idx, q in enumerate(questions):
            q_rec = build_question_record(
                quiz_id, idx,
                q["text"], q["options"], q["correct_index"],
                q.get("type", "multiple_choice"),
                q.get("explanation", ""),
                q.get("image_url", "")
            )
            msg_id = await quiz_service.db.write_record(q_rec)
            if msg_id:
                quiz_service.db.update_cache(msg_id, _format_for_cache(q_rec))

        # ── Muvaffaqiyat ──
        warn = ""
        if no_correct:
            nums = ", ".join(str(n) for n in no_correct[:5])
            warn = (
                f"\n\n⚠️ <b>Eslatma:</b> {len(no_correct)} ta savolda to'g'ri "
                f"javob belgilanmagan ({nums}). "
                f"Birinchi variant to'g'ri deb qabul qilindi."
            )

        # Inline tugmalar
        bot_username = (await message.bot.get_me()).username
        share_url = f"https://t.me/{bot_username}?startgroup=quiz_{quiz_id}"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="▶️ Guruhda boshlash",
                    switch_inline_query=f"quiz_start {quiz_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📋 Testlar ro'yxati",
                    switch_inline_query_current_chat="/quiz_list"
                ),
                InlineKeyboardButton(
                    text="📤 Ulashish",
                    url=share_url
                ),
            ],
        ])

        await wait_msg.edit_text(
            f"✅ <b>Test yaratildi!</b>\n\n"
            f"📚 <b>Nom:</b> {title}\n"
            f"🆔 <b>ID:</b> <code>{quiz_id}</code>\n"
            f"❓ <b>Savollar:</b> {len(questions)} ta\n"
            f"⏱ <b>Vaqt/savol:</b> {time_per_q} soniya\n"
            f"👤 <b>Yaratdi:</b> {created_by}"
            f"{warn}\n\n"
            f"▶️ Guruhda boshlash uchun:\n"
            f"<code>/quiz_start {quiz_id}</code>",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        await wait_msg.edit_text(
            f"❌ <b>Saqlashda xato:</b> {e}\n\n"
            f"DB guruh: <code>{config.DB_GROUP_ID}</code>",
            parse_mode="HTML"
        )

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

"""
╔══════════════════════════════════════════════════════╗
║         TELEGRAM QUIZ PLATFORM - ADMIN PANEL         ║
║         Streamlit Dashboard - Main Entry Point       ║
║                                                      ║
║  Ishga tushirish:  streamlit run main.py             ║
║  Bot background da avtomatik ishga tushadi!          ║
╚══════════════════════════════════════════════════════╝
"""
import streamlit as st
import json
import sys
import os
import csv
import io
import threading
import asyncio
import logging
from datetime import datetime

# Root papkani Python path ga qo'shish
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

from utils.config import config

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════
# BOT — BACKGROUND THREAD DA ISHLATISH
# ══════════════════════════════════════════════════════

def _run_bot_in_thread():
    """Botni alohida thread + event loop da ishlatadi."""
    async def _start_bot():
        from aiogram import Bot, Dispatcher, Router, BaseMiddleware
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        from aiogram.types import Message, BotCommand, TelegramObject
        from aiogram.filters import Command
        from typing import Callable, Dict, Any, Awaitable

        import bot.handlers as h_module
        from bot.group_manager import GroupManager
        from bot.leaderboard import LeaderboardService
        from services.quiz_service import QuizService
        from aiogram import F

        token = config.BOT_TOKEN
        if not token or token == "YOUR_BOT_TOKEN_HERE":
            logger.warning("BOT_TOKEN sozlanmagan — bot ishga tushmaydi")
            return

        bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        dp = Dispatcher()

        # ── Servislar ──────────────────────────────
        quiz_service        = QuizService()
        quiz_service.startup_load()  # quizzes.json + users.json → RAM
        group_manager       = GroupManager(bot)
        leaderboard_service = LeaderboardService(None)  # RAM dan o'qiydi

        # Middleware
        class MW(BaseMiddleware):
            async def __call__(
                self,
                handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
                event: TelegramObject,
                data: Dict[str, Any]
            ) -> Any:
                data["bot"]                  = bot
                data["quiz_service"]         = quiz_service
                data["group_manager"]        = group_manager
                data["leaderboard_service"]  = leaderboard_service
                return await handler(event, data)

        mw = MW()
        dp.message.middleware(mw)
        dp.callback_query.middleware(mw)

        # Har safar YANGI router yaratish
        new_router = Router(name="main_fresh")

        new_router.message.register(h_module.cmd_start,        Command("start"))
        new_router.message.register(h_module.cmd_help,         Command("help"))
        new_router.message.register(h_module.cmd_quiz_list,    Command("quiz_list"))
        new_router.message.register(h_module.cmd_quiz_start,   Command("quiz_start"))
        new_router.message.register(h_module.cmd_quiz_stop,    Command("quiz_stop"))
        new_router.message.register(h_module.cmd_leaderboard,  Command("leaderboard"))
        new_router.message.register(h_module.cmd_my_score,     Command("my_score"))
        new_router.message.register(h_module.cmd_quiz_history, Command("quiz_history"))
        new_router.message.register(h_module.cmd_create_quiz,  Command("create_quiz"))
        new_router.message.register(h_module.handle_document,  F.document)
        new_router.message.register(h_module.handle_text_quiz,
                                    F.text & F.text.startswith("Test nomi:"))
        new_router.callback_query.register(
            h_module.handle_answer, F.data.startswith("ans:")
        )

        dp.include_router(new_router)

        # Buyruqlar ro'yxati
        await bot.set_my_commands([
            BotCommand(command="start",        description="Boshlash"),
            BotCommand(command="help",         description="Yordam"),
            BotCommand(command="quiz_list",    description="Testlar ro'yxati"),
            BotCommand(command="quiz_start",   description="Test boshlash (admin)"),
            BotCommand(command="quiz_stop",    description="Testni to'xtatish (admin)"),
            BotCommand(command="create_quiz",  description="Test yaratish (admin)"),
            BotCommand(command="leaderboard",  description="Reyting"),
            BotCommand(command="my_score",     description="Mening natijalarim"),
            BotCommand(command="quiz_history", description="O'tgan testlar"),
        ])

        # ── STARTUP: quizzes.json + users.json → RAM ──
        from database.file_store import file_info
        fi = file_info()
        logger.info(
            f"🚀 Tayyor: {fi['quiz_count']} test, "
            f"{fi['users_count']} user | {fi['data_dir']}"
        )

        # Adminlarga xabar
        from database.file_store import file_info, get_all_quiz_ids
        stats = quiz_service.get_stats()
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"✅ <b>Bot ishga tushdi!</b>\n\n"
                    f"📚 Testlar: <b>{stats.get('quiz_count', 0)}</b>\n"
                    f"💾 Hajm: <b>{stats.get('quizzes_kb', 0)} KB</b>\n"
                    f"📁 Papka: <code>{stats.get('data_dir', '')}</code>\n\n"
                    f"/quiz_list — testlarni ko'rish\n"
                    f"/create_quiz — test yaratish"
                )
            except Exception:
                pass

        logger.info("✅ Bot polling boshlandi")
        try:
            await dp.start_polling(
                bot,
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True,
                handle_signals=False,
                close_bot_session=True,
            )
        except Exception as e:
            logger.error(f"Polling xatosi: {e}")
        finally:
            try:
                await bot.session.close()
            except Exception:
                pass

    # Yangi event loop (thread uchun)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_start_bot())
    except Exception as e:
        logger.error(f"Bot thread xatosi: {e}")
    finally:
        try:
            loop.close()
        except Exception:
            pass


def start_bot_background():
    """
    Botni background thread da bir martadan ishga tushiradi.
    Streamlit har render da bu funksiyani chaqiradi,
    lekin thread faqat bir marta yaratiladi.
    """
    # Thread allaqachon ishlamoqdami?
    for t in threading.enumerate():
        if t.name == "QuizBotThread":
            return  # Allaqachon ishlamoqda

    token = config.BOT_TOKEN
    if not token or token == "YOUR_BOT_TOKEN_HERE":
        return  # Token yo'q — ishlatma

    t = threading.Thread(
        target=_run_bot_in_thread,
        name="QuizBotThread",
        daemon=True   # Streamlit to'xtaganda bot ham to'xtaydi
    )
    t.start()
    logger.info("🚀 Bot background thread ishga tushdi")

# ══════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════
st.set_page_config(
    page_title="Quiz Platform Admin",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ══════════════════════════════════════════════════════
# CUSTOM CSS
# ══════════════════════════════════════════════════════
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
    }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1b2a 0%, #1b2838 100%);
        border-right: 1px solid rgba(99, 179, 237, 0.2);
    }
    div[data-testid="metric-container"] {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(99,179,237,0.2);
        border-radius: 12px;
        padding: 1rem;
        backdrop-filter: blur(10px);
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
    }
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(99,179,237,0.3);
        border-radius: 8px;
        color: #e2e8f0;
    }
    details {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(99,179,237,0.15);
        border-radius: 10px;
        padding: 0.5rem;
    }
    hr { border-color: rgba(99,179,237,0.1) !important; }
    h1, h2, h3 { color: #e2e8f0 !important; }
    p, label { color: #a0aec0; }
    div[data-testid="stAlert"] { border-radius: 8px; }
    .stSelectbox > div > div {
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(99,179,237,0.3);
        border-radius: 8px;
    }
    .logo-area {
        text-align: center;
        padding: 20px 0;
        border-bottom: 1px solid rgba(99,179,237,0.1);
        margin-bottom: 20px;
    }
    .status-online {
        display: inline-block;
        width: 8px; height: 8px;
        background: #48bb78;
        border-radius: 50%;
        margin-right: 6px;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
    }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
# AUTHENTICATION
# ══════════════════════════════════════════════════════
def check_auth() -> bool:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.markdown("""
    <div style='text-align:center; padding: 60px 0 30px;'>
        <div style='font-size: 4rem;'>🎯</div>
        <h1 style='color: #e2e8f0; margin: 0;'>Quiz Platform</h1>
        <p style='color: #718096;'>Admin Dashboard</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🔐 Kirish")
        username = st.text_input("Foydalanuvchi nomi", placeholder="admin")
        password = st.text_input("Parol", type="password", placeholder="••••••••")

        if st.button("Kirish", type="primary", use_container_width=True):
            if username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Noto'g'ri login yoki parol.")

        st.caption("Standart: admin / admin123 — .env faylida o'zgartiring")
    return False


# ══════════════════════════════════════════════════════
# DEMO DATA
# ══════════════════════════════════════════════════════
def load_demo_data() -> list:
    if "demo_data_loaded" in st.session_state:
        return st.session_state.get("db_records", [])

    now = datetime.utcnow().isoformat() + "Z"
    demo_records = [
        {"type": "QUIZ", "id": "quiz_demo_001", "title": "Present Simple Test",
         "description": "Ingliz tili grammatikasi", "created_by": "admin",
         "questions": 5, "time_per_question": 30, "created_at": now, "active": True},
        {"type": "QUIZ", "id": "quiz_demo_002", "title": "Python Basics",
         "description": "Python asoslari", "created_by": "admin",
         "questions": 4, "time_per_question": 45, "created_at": now, "active": True},
        {"type": "QUIZ", "id": "quiz_demo_003", "title": "Matematika 8-sinf",
         "description": "Algebra va geometriya", "created_by": "teacher_ali",
         "questions": 6, "time_per_question": 40, "created_at": now, "active": True},
        {"type": "QUESTION", "quiz_id": "quiz_demo_001", "index": 0,
         "text": "Which sentence is correct?",
         "options": ["He go to school", "He goes to school", "He going to school", "He goed to school"],
         "correct_index": 1, "question_type": "multiple_choice", "explanation": "3rd person singular adds -s"},
        {"type": "QUESTION", "quiz_id": "quiz_demo_001", "index": 1,
         "text": "She _____ English every day.",
         "options": ["study", "studies", "studied", "studying"],
         "correct_index": 1, "question_type": "multiple_choice", "explanation": "3rd person -ies"},
        {"type": "QUESTION", "quiz_id": "quiz_demo_001", "index": 2,
         "text": "Do you like pizza?", "options": ["True", "False"],
         "correct_index": 0, "question_type": "true_false", "explanation": ""},
        {"type": "QUESTION", "quiz_id": "quiz_demo_001", "index": 3,
         "text": "I _____ from London.", "options": ["am", "is", "are", "be"],
         "correct_index": 0, "question_type": "multiple_choice", "explanation": ""},
        {"type": "QUESTION", "quiz_id": "quiz_demo_001", "index": 4,
         "text": "They play football on Sundays.", "options": ["True", "False"],
         "correct_index": 0, "question_type": "true_false", "explanation": "Odatlar uchun present simple"},
        {"type": "QUESTION", "quiz_id": "quiz_demo_002", "index": 0,
         "text": "What is the output of print(type(42))?",
         "options": ["<class 'int'>", "<class 'str'>", "<class 'float'>", "<class 'num'>"],
         "correct_index": 0, "question_type": "multiple_choice", "explanation": "42 - integer"},
        {"type": "QUESTION", "quiz_id": "quiz_demo_002", "index": 1,
         "text": "Python is case-sensitive.", "options": ["True", "False"],
         "correct_index": 0, "question_type": "true_false", "explanation": ""},
        {"type": "QUESTION", "quiz_id": "quiz_demo_002", "index": 2,
         "text": "Which keyword defines a function?",
         "options": ["func", "def", "function", "define"],
         "correct_index": 1, "question_type": "multiple_choice", "explanation": "def kalit so'zi"},
        {"type": "QUESTION", "quiz_id": "quiz_demo_002", "index": 3,
         "text": "What does len([1,2,3]) return?",
         "options": ["2", "3", "4", "1"],
         "correct_index": 1, "question_type": "multiple_choice", "explanation": "3 ta element"},
        {"type": "SESSION", "id": "session_a1b2", "quiz_id": "quiz_demo_001",
         "quiz_title": "Present Simple Test", "group_id": -100123456789,
         "group_title": "English Class 10A", "started_by": 111111, "started_at": now},
        {"type": "SESSION", "id": "session_c3d4", "quiz_id": "quiz_demo_002",
         "quiz_title": "Python Basics", "group_id": -100987654321,
         "group_title": "CS Students Group", "started_by": 222222, "started_at": now},
        {"type": "SESSION", "id": "session_e5f6", "quiz_id": "quiz_demo_001",
         "quiz_title": "Present Simple Test", "group_id": -100111222333,
         "group_title": "10B sinf", "started_by": 333333, "started_at": now},
        {"type": "USER_SCORE", "session_id": "session_a1b2", "quiz_id": "quiz_demo_001",
         "user_id": 101, "username": "alice_dev", "first_name": "Alice",
         "correct": 5, "total": 5, "score": 100.0, "recorded_at": now},
        {"type": "USER_SCORE", "session_id": "session_a1b2", "quiz_id": "quiz_demo_001",
         "user_id": 102, "username": "bob_smith", "first_name": "Bob",
         "correct": 4, "total": 5, "score": 80.0, "recorded_at": now},
        {"type": "USER_SCORE", "session_id": "session_a1b2", "quiz_id": "quiz_demo_001",
         "user_id": 103, "username": "carol_j", "first_name": "Carol",
         "correct": 3, "total": 5, "score": 60.0, "recorded_at": now},
        {"type": "USER_SCORE", "session_id": "session_a1b2", "quiz_id": "quiz_demo_001",
         "user_id": 104, "username": "david_w", "first_name": "David",
         "correct": 2, "total": 5, "score": 40.0, "recorded_at": now},
        {"type": "USER_SCORE", "session_id": "session_c3d4", "quiz_id": "quiz_demo_002",
         "user_id": 101, "username": "alice_dev", "first_name": "Alice",
         "correct": 4, "total": 4, "score": 100.0, "recorded_at": now},
        {"type": "USER_SCORE", "session_id": "session_c3d4", "quiz_id": "quiz_demo_002",
         "user_id": 105, "username": "eve_coder", "first_name": "Eve",
         "correct": 3, "total": 4, "score": 75.0, "recorded_at": now},
        {"type": "USER_SCORE", "session_id": "session_c3d4", "quiz_id": "quiz_demo_002",
         "user_id": 106, "username": "frank_m", "first_name": "Frank",
         "correct": 2, "total": 4, "score": 50.0, "recorded_at": now},
        {"type": "USER_SCORE", "session_id": "session_e5f6", "quiz_id": "quiz_demo_001",
         "user_id": 107, "username": "gina_t", "first_name": "Gina",
         "correct": 5, "total": 5, "score": 100.0, "recorded_at": now},
        {"type": "USER_SCORE", "session_id": "session_e5f6", "quiz_id": "quiz_demo_001",
         "user_id": 108, "username": "harry_p", "first_name": "Harry",
         "correct": 1, "total": 5, "score": 20.0, "recorded_at": now},
        {"type": "RESULT", "session_id": "session_a1b2", "quiz_id": "quiz_demo_001",
         "group_id": -100123456789, "participants": 4, "avg_score": 70.0,
         "top_scorer": "alice_dev", "completed_at": now},
        {"type": "RESULT", "session_id": "session_c3d4", "quiz_id": "quiz_demo_002",
         "group_id": -100987654321, "participants": 3, "avg_score": 75.0,
         "top_scorer": "alice_dev", "completed_at": now},
        {"type": "RESULT", "session_id": "session_e5f6", "quiz_id": "quiz_demo_001",
         "group_id": -100111222333, "participants": 2, "avg_score": 60.0,
         "top_scorer": "gina_t", "completed_at": now},
        {"type": "LOG", "level": "INFO",    "message": "Bot ishga tushdi",                                  "context": {}, "timestamp": now},
        {"type": "LOG", "level": "INFO",    "message": "Quiz quiz_demo_001 yaratildi",                      "context": {}, "timestamp": now},
        {"type": "LOG", "level": "INFO",    "message": "Sessiya session_a1b2 boshlandi (English Class 10A)","context": {}, "timestamp": now},
        {"type": "LOG", "level": "INFO",    "message": "Sessiya session_a1b2 yakunlandi - 4 ishtirokchi",   "context": {}, "timestamp": now},
        {"type": "LOG", "level": "WARNING", "message": "User 107 kech javob berdi - rad etildi",            "context": {}, "timestamp": now},
        {"type": "LOG", "level": "INFO",    "message": "Sessiya session_c3d4 boshlandi (CS Students Group)","context": {}, "timestamp": now},
        {"type": "LOG", "level": "ERROR",   "message": "Telegram API timeout - session_e5f6 da xato",       "context": {}, "timestamp": now},
        {"type": "LOG", "level": "INFO",    "message": "Sessiya session_e5f6 yakunlandi - 2 ishtirokchi",   "context": {}, "timestamp": now},
    ]
    st.session_state.db_records = demo_records
    st.session_state.demo_data_loaded = True
    return demo_records


# ══════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════
def render_sidebar(db_records: list):
    with st.sidebar:
        st.markdown("""
        <div class='logo-area'>
            <div style='font-size:2.5rem;'>🎯</div>
            <div style='color:#e2e8f0; font-weight:700; font-size:1.1rem;'>Quiz Platform</div>
            <div style='color:#718096; font-size:0.75rem;'>Admin Dashboard v1.0</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style='background:rgba(72,187,120,0.1); border:1px solid rgba(72,187,120,0.3);
                    border-radius:8px; padding:8px 12px; margin-bottom:16px;'>
            <span class='status-online'></span>
            <span style='color:#68d391; font-size:0.85rem;'> Bot holati: Ishlamoqda</span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**Navigatsiya**")
        pages = {
            "🏠 Bosh sahifa":          "home",
            "✏️ Quiz Yaratish":         "creator",
            "📝 Quiz Tahrirlash":       "editor",
            "📊 Tahlil":                "analytics",
            "🏆 Foydalanuvchi ballari": "scores",
            "📋 Tizim loglari":         "logs",
        }
        if "current_page" not in st.session_state:
            st.session_state.current_page = "home"

        for label, key in pages.items():
            is_active = st.session_state.current_page == key
            if st.button(label, key=f"nav_{key}", use_container_width=True,
                         type="primary" if is_active else "secondary"):
                st.session_state.current_page = key
                st.rerun()

        st.divider()
        quizzes  = [r for r in db_records if r.get("type") == "QUIZ" and r.get("active", True)]
        scores   = [r for r in db_records if r.get("type") == "USER_SCORE"]
        sessions = [r for r in db_records if r.get("type") == "SESSION"]
        st.markdown("**Tezkor statistika**")
        st.caption(f"📚 Quizlar: **{len(quizzes)}**")
        st.caption(f"🎮 Sessiyalar: **{len(sessions)}**")
        st.caption(f"👥 Urinishlar: **{len(scores)}**")
        st.caption(f"🙋 O'yinchilar: **{len(set(s.get('user_id') for s in scores))}**")

        st.divider()
        with st.expander("📥 JSON yuklash"):
            uploaded = st.file_uploader("JSON fayl", type="json", label_visibility="collapsed")
            if uploaded:
                try:
                    data = json.load(uploaded)
                    if isinstance(data, list):
                        st.session_state.db_records = data
                        st.session_state.demo_data_loaded = True
                        st.success(f"✅ {len(data)} ta yozuv yuklandi!")
                        st.rerun()
                    else:
                        st.error("JSON massiv bo'lishi kerak!")
                except Exception as e:
                    st.error(f"Xato: {e}")

        if st.button("🚪 Chiqish", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()


# ══════════════════════════════════════════════════════
# PAGE: HOME
# ══════════════════════════════════════════════════════
def page_home(db_records: list):
    st.markdown("## 🏠 Bosh Sahifa")
    st.caption("Telegram Quiz Platform — Admin panelga xush kelibsiz")

    quizzes  = [r for r in db_records if r.get("type") == "QUIZ" and r.get("active", True)]
    scores   = [r for r in db_records if r.get("type") == "USER_SCORE"]
    sessions = [r for r in db_records if r.get("type") == "SESSION"]
    logs     = [r for r in db_records if r.get("type") == "LOG"]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📚 Quizlar",     len(quizzes),  "+3 bu hafta")
    c2.metric("🎮 Sessiyalar",  len(sessions), "+3 bu hafta")
    c3.metric("👥 Urinishlar",  len(scores))
    c4.metric("🙋 O'yinchilar", len(set(s.get("user_id") for s in scores)))
    avg = sum(s.get("score", 0) for s in scores) / len(scores) if scores else 0
    c5.metric("📈 O'rtacha ball", f"{avg:.1f}%")

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📚 So'nggi quizlar")
        for q in quizzes[-5:][::-1]:
            st.markdown(f"**{q.get('title','Nomsiz')}**")
            a, b, c = st.columns(3)
            a.caption(f"🆔 `{q.get('id','?')[-12:]}`")
            b.caption(f"❓ {q.get('questions',0)} savol")
            c.caption(f"⏱ {q.get('time_per_question',30)}s")
            st.divider()

    with col2:
        st.markdown("### 🏆 Top o'yinchilar")
        best = {}
        for s in scores:
            uid = s.get("user_id")
            sc  = s.get("score", 0)
            if uid not in best or sc > best[uid].get("score", 0):
                best[uid] = s
        top = sorted(best.values(), key=lambda x: x.get("score", 0), reverse=True)[:5]
        for i, u in enumerate(top):
            emojis = ["🥇","🥈","🥉","4.","5."]
            name   = u.get("username") or u.get("first_name","?")
            a, b   = st.columns([3,1])
            a.markdown(f"{emojis[i]} **{name}**")
            b.markdown(f"**{u.get('score',0):.0f}%**")

    st.divider()
    st.markdown("### 📋 So'nggi faoliyat")
    icons = {"INFO":"ℹ️","WARNING":"⚠️","ERROR":"🔴"}
    for log in reversed(logs[-8:]):
        ts   = log.get("timestamp","")[:16].replace("T"," ")
        icon = icons.get(log.get("level","INFO"),"ℹ️")
        st.caption(f"{icon} `{ts}` — {log.get('message','')}")


# ══════════════════════════════════════════════════════
# PAGE: QUIZ CREATOR
# ══════════════════════════════════════════════════════
def page_quiz_creator():
    st.markdown("## ✏️ Quiz Yaratish")
    st.caption("Yangi quiz yarating — savollar, variantlar va taymer bilan.")

    st.markdown("### 📋 Quiz ma'lumotlari")
    c1, c2 = st.columns(2)
    with c1:
        title      = st.text_input("Quiz nomi *", placeholder="masalan: Present Simple Test")
        created_by = st.text_input("Yaratuvchi", value="admin")
    with c2:
        description = st.text_area("Tavsif", placeholder="Qisqacha tavsif...", height=100)
        time_per_q  = st.slider("⏱ Har savol uchun sekund", 10, 120, 30, step=5)

    st.divider()
    st.markdown("### ❓ Savollar")

    if "questions" not in st.session_state:
        st.session_state.questions = []

    with st.expander("➕ Yangi savol qo'shish", expanded=len(st.session_state.questions) == 0):
        q_type = st.selectbox("Savol turi",
                              ["multiple_choice","true_false","fill_in_blank"],
                              format_func=lambda x: {
                                  "multiple_choice": "📋 Ko'p tanlovli (4 variant)",
                                  "true_false":      "✅ Ha / Yo'q",
                                  "fill_in_blank":   "✍️ Bo'sh to'ldirish"
                              }[x])
        q_text    = st.text_area("Savol matni *", placeholder="Savolingizni kiriting...", height=80)
        image_url = st.text_input("Rasm URL (ixtiyoriy)", placeholder="https://...")
        options, correct_index = [], 0

        if q_type == "multiple_choice":
            st.markdown("**Javob variantlari:**")
            c1, c2 = st.columns(2)
            with c1:
                oa = st.text_input("A)", placeholder="Variant A")
                ob = st.text_input("B)", placeholder="Variant B")
            with c2:
                oc = st.text_input("C)", placeholder="Variant C")
                od = st.text_input("D)", placeholder="Variant D")
            options = [oa, ob, oc, od]
            cl      = st.radio("✅ To'g'ri javob", ["A","B","C","D"], horizontal=True)
            correct_index = {"A":0,"B":1,"C":2,"D":3}[cl]

        elif q_type == "true_false":
            options = ["Ha","Yo'q"]
            ct = st.radio("✅ To'g'ri javob", ["Ha","Yo'q"], horizontal=True)
            correct_index = 0 if ct == "Ha" else 1

        elif q_type == "fill_in_blank":
            ans = st.text_input("To'g'ri javob *", placeholder="Aniq to'g'ri javob")
            options = [ans,"","",""]
            correct_index = 0

        explanation = st.text_input("💡 Tushuntirish", placeholder="Ixtiyoriy...")

        if st.button("➕ Savol qo'shish", type="primary", use_container_width=True):
            if not q_text.strip():
                st.error("Savol matni majburiy!")
            elif q_type == "multiple_choice" and not all([options[0], options[1]]):
                st.error("Kamida A va B variantlari to'ldirilishi kerak!")
            elif q_type == "fill_in_blank" and not options[0]:
                st.error("To'g'ri javob kiritilishi shart!")
            else:
                st.session_state.questions.append({
                    "text": q_text.strip(),
                    "type": q_type,
                    "options": [o for o in options if o.strip()],
                    "correct_index": correct_index,
                    "explanation": explanation.strip(),
                    "image_url": image_url.strip()
                })
                st.success(f"✅ {len(st.session_state.questions)}-savol qo'shildi!")
                st.rerun()

    if st.session_state.questions:
        st.markdown(f"**{len(st.session_state.questions)} ta savol:**")
        icons_map = {"multiple_choice":"📋","true_false":"✅","fill_in_blank":"✍️"}
        for i, q in enumerate(st.session_state.questions):
            c1, c2, c3 = st.columns([0.05, 0.85, 0.1])
            c1.markdown(f"**{i+1}**")
            icon = icons_map.get(q.get("type",""),"❓")
            c2.markdown(f"{icon} {q['text'][:80]}{'...' if len(q['text'])>80 else ''}")
            if c3.button("🗑", key=f"del_{i}"):
                st.session_state.questions.pop(i)
                st.rerun()
            st.divider()
        if st.button("🔄 Hammasini tozalash", use_container_width=True):
            st.session_state.questions = []
            st.rerun()
    else:
        st.info("📝 Hali savol yo'q.")

    st.divider()
    with st.expander("📥 JSON dan import"):
        json_input = st.text_area("JSON massiv", height=150,
                                  placeholder='[{"text":"...","options":[...],"correct_index":0}]')
        if st.button("📥 Import"):
            try:
                imported = json.loads(json_input)
                if isinstance(imported, list):
                    for q in imported:
                        if "text" in q and "options" in q:
                            st.session_state.questions.append(q)
                    st.success(f"✅ {len(imported)} ta savol import!")
                    st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"JSON xato: {e}")

    st.divider()
    st.markdown("### 🚀 Quizni saqlash")
    can_submit = bool(title.strip() and st.session_state.questions)
    if not can_submit:
        st.warning("⚠️ Quiz nomi va kamida bitta savol kerak.")

    if st.button("💾 Quizni bazaga saqlash", type="primary",
                 use_container_width=True, disabled=not can_submit):
        from utils.helpers import generate_id, build_quiz_record, build_question_record
        quiz_id  = generate_id("quiz")
        q_record = build_quiz_record(quiz_id, title.strip(), description.strip(),
                                     created_by or "admin",
                                     len(st.session_state.questions), time_per_q)
        q_list = [build_question_record(
            quiz_id, i, q["text"], q["options"], q["correct_index"],
            q.get("type","multiple_choice"), q.get("explanation",""), q.get("image_url","")
        ) for i, q in enumerate(st.session_state.questions)]

        st.success(f"✅ Quiz **{title}** tayyor! ID: `{quiz_id}`")
        st.markdown("**Telegram DB ga yuboriladigan yozuvlar:**")
        st.json([q_record] + q_list)
        st.session_state.questions = []


# ══════════════════════════════════════════════════════
# PAGE: QUIZ EDITOR
# ══════════════════════════════════════════════════════
def page_quiz_editor(db_records: list):
    st.markdown("## 📝 Quiz Tahrirlash")
    st.caption("Mavjud quizlarni ko'ring, tahrirlang yoki o'chiring.")

    quizzes   = [r for r in db_records if r.get("type") == "QUIZ" and r.get("active", True)]
    questions = [r for r in db_records if r.get("type") == "QUESTION"]

    if not quizzes:
        st.info("📭 Bazada quiz yo'q. Avval **Quiz Yaratish** da quiz yarating!")
        return

    quiz_map    = {q["id"]: q for q in quizzes}
    selected_id = st.selectbox("Quiz tanlang", list(quiz_map.keys()),
                                format_func=lambda x: f"{quiz_map[x].get('title','?')} ({x})")
    quiz    = quiz_map[selected_id]
    quiz_qs = sorted([q for q in questions if q.get("quiz_id") == selected_id],
                     key=lambda x: x.get("index", 0))

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Savollar",   len(quiz_qs))
    c2.metric("Vaqt/savol", f"{quiz.get('time_per_question',30)}s")
    c3.metric("Yaratuvchi", quiz.get("created_by","?"))
    c4.metric("Holat",      "✅ Faol" if quiz.get("active", True) else "❌ O'chirilgan")

    st.divider()
    with st.expander("✏️ Ma'lumotlarni tahrirlash"):
        nt = st.text_input("Nom", value=quiz.get("title",""))
        nd = st.text_area("Tavsif", value=quiz.get("description",""), height=80)
        nv = st.slider("Sekund/savol", 10, 120, quiz.get("time_per_question",30), step=5)
        if st.button("💾 Saqlash"):
            st.json({"type":"QUIZ","id":selected_id,"title":nt,
                     "description":nd,"time_per_question":nv,"active":True})
            st.success("✅ Yangilash yozuvi yaratildi.")

    st.markdown(f"### ❓ Savollar ({len(quiz_qs)})")
    if not quiz_qs:
        st.warning("Savollar topilmadi.")
    else:
        for i, q in enumerate(quiz_qs):
            with st.expander(f"S{i+1}: {q.get('text','')[:65]}"):
                st.markdown(f"**Tur:** {q.get('question_type','multiple_choice')}")
                st.markdown(f"**Savol:** {q.get('text','')}")
                opts = q.get("options",[])
                ci   = q.get("correct_index",0)
                for j, opt in enumerate(opts):
                    mark = "✅" if j == ci else "　"
                    lbl  = ["A","B","C","D"][j] if j < 4 else str(j+1)
                    st.markdown(f"{mark} **{lbl})** {opt}")
                if q.get("explanation"):
                    st.info(f"💡 {q['explanation']}")

    st.divider()
    st.markdown("### 🗑️ Xavfli zona")
    with st.expander("⚠️ Quizni o'chirish"):
        st.warning(f"**{quiz.get('title')}** soft-delete qilinadi.")
        confirm = st.text_input("Tasdiqlash uchun nomni kiriting:")
        if st.button("🗑️ O'chirish", type="primary"):
            if confirm == quiz.get("title"):
                st.json({"type":"QUIZ","id":selected_id,"active":False,
                         "deleted_at":datetime.utcnow().isoformat()+"Z"})
                st.error(f"☠️ Belgilandi: **{quiz.get('title')}**")
            else:
                st.error("Nom mos kelmadi.")

    st.divider()
    st.download_button("📥 JSON yuklab olish",
                       json.dumps({"quiz":quiz,"questions":quiz_qs}, ensure_ascii=False, indent=2),
                       f"quiz_{selected_id}.json", "application/json", use_container_width=True)


# ══════════════════════════════════════════════════════
# PAGE: ANALYTICS
# ══════════════════════════════════════════════════════
def page_analytics(db_records: list):
    from collections import defaultdict
    st.markdown("## 📊 Tahlil")
    st.caption("Quiz statistikasi, ishtirok va natijalar tahlili.")

    quizzes  = [r for r in db_records if r.get("type") == "QUIZ" and r.get("active", True)]
    sessions = [r for r in db_records if r.get("type") == "SESSION"]
    scores   = [r for r in db_records if r.get("type") == "USER_SCORE"]

    st.markdown("### 🌐 Umumiy")
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("📚 Quizlar",    len(quizzes))
    c2.metric("🎮 Sessiyalar", len(sessions))
    c3.metric("👥 Urinishlar", len(scores))
    c4.metric("🙋 Unikal",     len(set(s.get("user_id") for s in scores)))
    avg_all = sum(s.get("score",0) for s in scores) / len(scores) if scores else 0
    c5.metric("📈 O'rtacha",   f"{avg_all:.1f}%")
    st.divider()

    if not quizzes:
        st.info("Hali ma'lumot yo'q.")
        return

    quiz_labels = {q["id"]: q.get("title", q["id"]) for q in quizzes}
    sel = st.selectbox("Quiz tanlang", ["all"]+list(quiz_labels.keys()),
                       format_func=lambda x: "🌍 Barchasi" if x=="all" else quiz_labels.get(x,x))
    fs = scores   if sel=="all" else [s for s in scores   if s.get("quiz_id")==sel]
    fss= sessions if sel=="all" else [s for s in sessions if s.get("quiz_id")==sel]

    st.divider()
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("🎮 Sessiyalar",   len(fss))
    c2.metric("👥 Ishtirokchi",  len(fs))
    c3.metric("🙋 Unikal",       len(set(s.get("user_id") for s in fs)))
    hi = max((s.get("score",0) for s in fs), default=0)
    c4.metric("🏆 Eng yuqori",   f"{hi:.0f}%")

    if fs:
        st.divider()
        st.markdown("#### 📊 Ball taqsimoti")
        buckets = defaultdict(int)
        labels  = ["0-20","21-40","41-60","61-80","81-100"]
        for s in fs:
            sc = s.get("score",0)
            if sc<=20:   buckets["0-20"]  +=1
            elif sc<=40: buckets["21-40"] +=1
            elif sc<=60: buckets["41-60"] +=1
            elif sc<=80: buckets["61-80"] +=1
            else:        buckets["81-100"]+=1
        cols = st.columns(5)
        for i,lbl in enumerate(labels):
            cnt = buckets[lbl]
            cols[i].metric(lbl, cnt, f"{cnt/len(fs)*100:.1f}%")
        passed   = sum(1 for s in fs if s.get("score",0)>=60)
        pass_pct = passed/len(fs)*100
        st.progress(pass_pct/100, text=f"O'tish darajasi (≥60%): {pass_pct:.1f}% — {passed}/{len(fs)}")

        st.divider()
        st.markdown("#### 🏆 Top o'yinchilar")
        best = {}
        for s in fs:
            uid = s.get("user_id")
            if uid not in best or s.get("score",0) > best[uid].get("score",0):
                best[uid] = s
        top    = sorted(best.values(), key=lambda x: x.get("score",0), reverse=True)[:10]
        emojis = ["🥇","🥈","🥉"]+[f"{i}." for i in range(4,11)]
        for i,u in enumerate(top):
            name = u.get("username") or u.get("first_name","?")
            c1,c2,c3,c4 = st.columns([0.5,3,1.5,1.5])
            c1.markdown(f"**{emojis[i]}**")
            c2.markdown(f"**{name}**")
            c3.markdown(f"✅ {u.get('correct',0)}/{u.get('total',0)}")
            c4.markdown(f"**{u.get('score',0):.0f}%**")

        st.divider()
        out = io.StringIO()
        w   = csv.DictWriter(out, fieldnames=["user_id","username","first_name",
                                               "quiz_id","session_id","correct","total","score"])
        w.writeheader()
        for s in fs: w.writerow({k:s.get(k,"") for k in w.fieldnames})
        st.download_button("📥 CSV yuklab olish", out.getvalue(),
                           f"tahlil_{sel}.csv", "text/csv", use_container_width=True)


# ══════════════════════════════════════════════════════
# PAGE: USER SCORES
# ══════════════════════════════════════════════════════
def page_user_scores(db_records: list):
    st.markdown("## 🏆 Foydalanuvchi Ballari")
    st.caption("Barcha sessiyalardagi natijalar.")

    scores  = [r for r in db_records if r.get("type") == "USER_SCORE"]
    quizzes = {q["id"]: q for q in db_records if q.get("type") == "QUIZ"}

    if not scores:
        st.info("Hali ball yozilmagan.")
        return

    c1,c2 = st.columns(2)
    with c1:
        qf = st.selectbox("Quiz filter", ["All"]+list(set(s.get("quiz_id","") for s in scores)),
                          format_func=lambda x: "Barchasi" if x=="All" else quizzes.get(x,{}).get("title",x))
    with c2:
        sf = st.selectbox("Saralash", ["Ball (yuqori→past)","Ball (past→yuqori)","Ism A→Z"])

    filtered = scores if qf=="All" else [s for s in scores if s.get("quiz_id")==qf]
    sm = {"Ball (yuqori→past)":lambda x:-x.get("score",0),
          "Ball (past→yuqori)":lambda x:x.get("score",0),
          "Ism A→Z":lambda x:(x.get("username") or x.get("first_name","")).lower()}
    filtered = sorted(filtered, key=sm[sf])

    st.markdown(f"**{len(filtered)} ta yozuv**")
    st.divider()

    for s in filtered:
        c1,c2,c3,c4,c5 = st.columns([2,2,1.5,1.5,2])
        name   = s.get("username") or s.get("first_name","?")
        qtitle = quizzes.get(s.get("quiz_id",""),{}).get("title",s.get("quiz_id","?")[:20])
        sc     = s.get("score",0)
        color  = "green" if sc>=60 else "orange" if sc>=40 else "red"
        c1.markdown(f"**{name}**"); c1.caption(f"ID: {s.get('user_id','?')}")
        c2.markdown(f"📚 {qtitle[:25]}")
        c3.markdown(f"✅ {s.get('correct',0)}/{s.get('total',0)}")
        c4.markdown(f"**:{color}[{sc:.0f}%]**")
        c5.caption(s.get("recorded_at","")[:16].replace("T"," "))
        st.divider()

    out = io.StringIO()
    w   = csv.DictWriter(out, fieldnames=["username","first_name","user_id","quiz_id","correct","total","score"])
    w.writeheader()
    for s in filtered: w.writerow({k:s.get(k,"") for k in w.fieldnames})
    st.download_button("📥 CSV yuklab olish", out.getvalue(),
                       "balllar.csv","text/csv", use_container_width=True)


# ══════════════════════════════════════════════════════
# PAGE: LOGS
# ══════════════════════════════════════════════════════
def page_logs(db_records: list):
    st.markdown("## 📋 Tizim Loglari")
    st.caption("Bot faoliyati va tizim hodisalari.")

    logs = [r for r in db_records if r.get("type") == "LOG"]
    if not logs:
        st.info("Loglar hali yo'q.")
        return

    lf       = st.multiselect("Daraja", ["INFO","WARNING","ERROR"], default=["INFO","WARNING","ERROR"])
    filtered = list(reversed([l for l in logs if l.get("level","INFO") in lf]))
    st.markdown(f"**{len(filtered)} ta yozuv**")
    st.divider()

    colors = {"INFO":"blue","WARNING":"orange","ERROR":"red"}
    icons  = {"INFO":"ℹ️","WARNING":"⚠️","ERROR":"🔴"}
    for log in filtered:
        lv = log.get("level","INFO")
        c1,c2,c3 = st.columns([1,5,1.5])
        c1.markdown(f":{colors.get(lv,'blue')}[**{icons.get(lv,'ℹ️')} {lv}**]")
        c2.markdown(log.get("message",""))
        if log.get("context"): c2.caption(str(log["context"]))
        c3.caption(log.get("timestamp","")[:19].replace("T"," "))
        st.divider()


# ══════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════
def bot_status_widget():
    """Sidebar da bot holati ko'rsatadi."""
    token = config.BOT_TOKEN
    token_ok = token and token != "YOUR_BOT_TOKEN_HERE"

    # Thread ishlamoqdami?
    bot_running = any(t.name == "QuizBotThread" for t in threading.enumerate())

    if token_ok and bot_running:
        st.markdown("""
        <div style='background:rgba(72,187,120,0.15); border:1px solid rgba(72,187,120,0.4);
                    border-radius:8px; padding:10px 14px; margin-bottom:12px;'>
            <span style='color:#68d391; font-size:0.9rem;'>🟢 <b>Bot: Ishlamoqda</b></span>
        </div>
        """, unsafe_allow_html=True)
    elif token_ok and not bot_running:
        st.markdown("""
        <div style='background:rgba(237,137,54,0.15); border:1px solid rgba(237,137,54,0.4);
                    border-radius:8px; padding:10px 14px; margin-bottom:12px;'>
            <span style='color:#f6ad55; font-size:0.9rem;'>🟡 <b>Bot: Ishga tushmoqda...</b></span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style='background:rgba(245,101,101,0.15); border:1px solid rgba(245,101,101,0.4);
                    border-radius:8px; padding:10px 14px; margin-bottom:12px;'>
            <span style='color:#fc8181; font-size:0.9rem;'>🔴 <b>Bot: Token yo'q</b></span>
        </div>
        """, unsafe_allow_html=True)
        st.caption("Secrets da BOT_TOKEN kiriting")


def main():
    # ── Botni background da ishga tushirish ──
    # (Streamlit har render qilganda chaqiriladi,
    #  lekin thread faqat bir marta yaratiladi)
    start_bot_background()

    if not check_auth():
        return

    db_records = load_demo_data()

    # ── Sidebar ──
    with st.sidebar:
        st.markdown("""
        <div style='text-align:center; padding:16px 0 12px;
                    border-bottom:1px solid rgba(99,179,237,0.1); margin-bottom:16px;'>
            <div style='font-size:2.2rem;'>🎯</div>
            <div style='color:#e2e8f0; font-weight:700; font-size:1rem;'>Quiz Platform</div>
            <div style='color:#718096; font-size:0.72rem;'>Admin Dashboard v1.0</div>
        </div>
        """, unsafe_allow_html=True)

        # Bot holati
        bot_status_widget()

        st.markdown("**Navigatsiya**")
        pages = {
            "🏠 Bosh sahifa":          "home",
            "✏️ Quiz Yaratish":         "creator",
            "📝 Quiz Tahrirlash":       "editor",
            "📊 Tahlil":                "analytics",
            "🏆 Foydalanuvchi ballari": "scores",
            "📋 Tizim loglari":         "logs",
        }
        if "current_page" not in st.session_state:
            st.session_state.current_page = "home"

        for label, key in pages.items():
            is_active = st.session_state.current_page == key
            if st.button(label, key=f"nav_{key}", use_container_width=True,
                         type="primary" if is_active else "secondary"):
                st.session_state.current_page = key
                st.rerun()

        st.divider()

        quizzes  = [r for r in db_records if r.get("type") == "QUIZ" and r.get("active", True)]
        scores   = [r for r in db_records if r.get("type") == "USER_SCORE"]
        sessions = [r for r in db_records if r.get("type") == "SESSION"]

        st.markdown("**Tezkor statistika**")
        st.caption(f"📚 Quizlar: **{len(quizzes)}**")
        st.caption(f"🎮 Sessiyalar: **{len(sessions)}**")
        st.caption(f"👥 Urinishlar: **{len(scores)}**")
        st.caption(f"🙋 O'yinchilar: **{len(set(s.get('user_id') for s in scores))}**")

        st.divider()

        with st.expander("📥 JSON yuklash"):
            uploaded = st.file_uploader("JSON fayl", type="json", label_visibility="collapsed")
            if uploaded:
                try:
                    data = json.load(uploaded)
                    if isinstance(data, list):
                        st.session_state.db_records = data
                        st.session_state.demo_data_loaded = True
                        st.success(f"✅ {len(data)} ta yozuv yuklandi!")
                        st.rerun()
                    else:
                        st.error("JSON massiv bo'lishi kerak!")
                except Exception as e:
                    st.error(f"Xato: {e}")

        if st.button("🚪 Chiqish", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    # ── Sahifa routing ──
    page = st.session_state.get("current_page", "home")
    routing = {
        "home":      lambda: page_home(db_records),
        "creator":   lambda: page_quiz_creator(),
        "editor":    lambda: page_quiz_editor(db_records),
        "analytics": lambda: page_analytics(db_records),
        "scores":    lambda: page_user_scores(db_records),
        "logs":      lambda: page_logs(db_records),
    }
    routing.get(page, routing["home"])()


if __name__ == "__main__":
    main()

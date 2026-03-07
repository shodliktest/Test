"""
Admin Panel - Main Streamlit Application
Telegram Quiz Platform Administration Dashboard
"""
import streamlit as st
import json
import sys
import os
from datetime import datetime

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import config

# ── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Quiz Platform Admin",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Inject Custom CSS ──────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main background */
    .stApp {
        background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1b2a 0%, #1b2838 100%);
        border-right: 1px solid rgba(99, 179, 237, 0.2);
    }

    /* Cards / containers */
    div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] {
        gap: 1rem;
    }

    /* Metric cards */
    div[data-testid="metric-container"] {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(99,179,237,0.2);
        border-radius: 12px;
        padding: 1rem;
        backdrop-filter: blur(10px);
    }

    /* Buttons */
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

    /* Text inputs */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(99,179,237,0.3);
        border-radius: 8px;
        color: #e2e8f0;
    }

    /* Expanders */
    details {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(99,179,237,0.15);
        border-radius: 10px;
        padding: 0.5rem;
    }

    /* Divider */
    hr {
        border-color: rgba(99,179,237,0.1) !important;
    }

    /* Headers */
    h1, h2, h3 { color: #e2e8f0 !important; }
    p, label { color: #a0aec0; }

    /* Success/Error/Info */
    div[data-testid="stAlert"] {
        border-radius: 8px;
    }

    /* Select boxes */
    .stSelectbox > div > div {
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(99,179,237,0.3);
        border-radius: 8px;
    }

    /* Sidebar nav */
    .nav-item {
        padding: 8px 12px;
        border-radius: 8px;
        margin: 2px 0;
        cursor: pointer;
        transition: all 0.2s;
        color: #a0aec0;
        font-size: 0.9rem;
    }
    .nav-item:hover, .nav-item.active {
        background: rgba(102, 126, 234, 0.2);
        color: #e2e8f0;
    }

    /* Logo area */
    .logo-area {
        text-align: center;
        padding: 20px 0;
        border-bottom: 1px solid rgba(99,179,237,0.1);
        margin-bottom: 20px;
    }

    /* Status badge */
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


# ── Authentication ─────────────────────────────────────────────────────────────
def check_auth():
    """Simple session-based authentication."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    # Login form
    st.markdown("""
    <div style='text-align:center; padding: 60px 0 30px;'>
        <div style='font-size: 4rem;'>🎯</div>
        <h1 style='color: #e2e8f0; margin: 0;'>Quiz Platform</h1>
        <p style='color: #718096;'>Admin Dashboard</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🔐 Sign In")
        username = st.text_input("Username", placeholder="Enter username")
        password = st.text_input("Password", type="password", placeholder="Enter password")

        if st.button("Sign In", type="primary", use_container_width=True):
            if username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Invalid credentials.")

        st.caption("Default: admin / admin123 — Change in environment variables")
    return False


# ── Load Mock Data (for demo without live bot) ─────────────────────────────────
def load_demo_data():
    """Load sample data for demonstration when no live bot is connected."""
    if "demo_data_loaded" in st.session_state:
        return st.session_state.get("db_records", [])

    now = datetime.utcnow().isoformat() + "Z"
    demo_records = [
        # Quizzes
        {"type": "QUIZ", "id": "quiz_demo_001", "title": "Present Simple Test",
         "description": "Basic English grammar quiz", "created_by": "admin",
         "questions": 5, "time_per_question": 30, "created_at": now, "active": True},
        {"type": "QUIZ", "id": "quiz_demo_002", "title": "Python Basics",
         "description": "Python programming fundamentals", "created_by": "admin",
         "questions": 4, "time_per_question": 45, "created_at": now, "active": True},

        # Questions for quiz_demo_001
        {"type": "QUESTION", "quiz_id": "quiz_demo_001", "index": 0,
         "text": "Which sentence is correct?", "options": ["He go to school", "He goes to school", "He going to school", "He goed to school"],
         "correct_index": 1, "question_type": "multiple_choice", "explanation": "Third person singular adds -s"},
        {"type": "QUESTION", "quiz_id": "quiz_demo_001", "index": 1,
         "text": "She _____ English every day.", "options": ["study", "studies", "studied", "studying"],
         "correct_index": 1, "question_type": "multiple_choice", "explanation": "Third person singular uses -ies"},
        {"type": "QUESTION", "quiz_id": "quiz_demo_001", "index": 2,
         "text": "Do you like pizza?", "options": ["True", "False"],
         "correct_index": 0, "question_type": "true_false", "explanation": ""},
        {"type": "QUESTION", "quiz_id": "quiz_demo_001", "index": 3,
         "text": "I _____ from London.", "options": ["am", "is", "are", "be"],
         "correct_index": 0, "question_type": "multiple_choice", "explanation": ""},
        {"type": "QUESTION", "quiz_id": "quiz_demo_001", "index": 4,
         "text": "They play football on Sundays. (True/False)", "options": ["True", "False"],
         "correct_index": 0, "question_type": "true_false", "explanation": "Present simple for habits"},

        # Questions for quiz_demo_002
        {"type": "QUESTION", "quiz_id": "quiz_demo_002", "index": 0,
         "text": "What is the output of print(type(42))?", "options": ["<class 'int'>", "<class 'str'>", "<class 'float'>", "<class 'num'>"],
         "correct_index": 0, "question_type": "multiple_choice", "explanation": "42 is an integer"},
        {"type": "QUESTION", "quiz_id": "quiz_demo_002", "index": 1,
         "text": "Python is case-sensitive.", "options": ["True", "False"],
         "correct_index": 0, "question_type": "true_false", "explanation": "Variable and function names are case-sensitive"},
        {"type": "QUESTION", "quiz_id": "quiz_demo_002", "index": 2,
         "text": "Which keyword is used to define a function?", "options": ["func", "def", "function", "define"],
         "correct_index": 1, "question_type": "multiple_choice", "explanation": "def keyword defines functions"},
        {"type": "QUESTION", "quiz_id": "quiz_demo_002", "index": 3,
         "text": "What does len([1,2,3]) return?", "options": ["2", "3", "4", "1"],
         "correct_index": 1, "question_type": "multiple_choice", "explanation": "len() returns the number of elements"},

        # Sessions
        {"type": "SESSION", "id": "session_a1b2", "quiz_id": "quiz_demo_001",
         "quiz_title": "Present Simple Test", "group_id": -100123456789,
         "group_title": "English Class 10A", "started_by": 111111, "started_at": now},
        {"type": "SESSION", "id": "session_c3d4", "quiz_id": "quiz_demo_002",
         "quiz_title": "Python Basics", "group_id": -100987654321,
         "group_title": "CS Students Group", "started_by": 222222, "started_at": now},

        # User scores
        {"type": "USER_SCORE", "session_id": "session_a1b2", "quiz_id": "quiz_demo_001",
         "user_id": 101, "username": "alice_dev", "first_name": "Alice",
         "correct": 5, "total": 5, "score": 100.0, "recorded_at": now},
        {"type": "USER_SCORE", "session_id": "session_a1b2", "quiz_id": "quiz_demo_001",
         "user_id": 102, "username": "bob_smith", "first_name": "Bob",
         "correct": 4, "total": 5, "score": 80.0, "recorded_at": now},
        {"type": "USER_SCORE", "session_id": "session_a1b2", "quiz_id": "quiz_demo_001",
         "user_id": 103, "username": "carol_jones", "first_name": "Carol",
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

        # Results
        {"type": "RESULT", "session_id": "session_a1b2", "quiz_id": "quiz_demo_001",
         "group_id": -100123456789, "participants": 4, "avg_score": 70.0,
         "top_scorer": "alice_dev", "completed_at": now},
        {"type": "RESULT", "session_id": "session_c3d4", "quiz_id": "quiz_demo_002",
         "group_id": -100987654321, "participants": 3, "avg_score": 75.0,
         "top_scorer": "alice_dev", "completed_at": now},

        # Logs
        {"type": "LOG", "level": "INFO", "message": "Bot started", "context": {}, "timestamp": now},
        {"type": "LOG", "level": "INFO", "message": "Quiz quiz_demo_001 created", "context": {}, "timestamp": now},
        {"type": "LOG", "level": "INFO", "message": "Session session_a1b2 started in group -100123456789", "context": {}, "timestamp": now},
        {"type": "LOG", "level": "INFO", "message": "Session session_a1b2 completed with 4 participants", "context": {}, "timestamp": now},
        {"type": "LOG", "level": "WARNING", "message": "User 107 attempted late answer in session session_a1b2", "context": {}, "timestamp": now},
    ]

    st.session_state.db_records = demo_records
    st.session_state.demo_data_loaded = True
    return demo_records


# ── Main Application ───────────────────────────────────────────────────────────
def main():
    if not check_auth():
        return

    # Load data
    db_records = load_demo_data()

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("""
        <div class='logo-area'>
            <div style='font-size:2.5rem;'>🎯</div>
            <div style='color:#e2e8f0; font-weight:700; font-size:1.1rem;'>Quiz Platform</div>
            <div style='color:#718096; font-size:0.75rem;'>Admin Dashboard</div>
        </div>
        """, unsafe_allow_html=True)

        # Bot status
        st.markdown("""
        <div style='background: rgba(72,187,120,0.1); border: 1px solid rgba(72,187,120,0.3);
                    border-radius:8px; padding: 8px 12px; margin-bottom: 16px;'>
            <span class='status-online'></span>
            <span style='color:#68d391; font-size:0.85rem;'> Bot Status: Online</span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**Navigation**")
        pages = {
            "🏠 Home": "home",
            "✏️ Quiz Creator": "creator",
            "📝 Quiz Editor": "editor",
            "📊 Analytics": "analytics",
            "🏆 User Scores": "scores",
            "📋 System Logs": "logs",
        }

        if "current_page" not in st.session_state:
            st.session_state.current_page = "home"

        for label, page_key in pages.items():
            is_active = st.session_state.current_page == page_key
            btn_type = "primary" if is_active else "secondary"
            if st.button(label, key=f"nav_{page_key}", use_container_width=True,
                         type=btn_type):
                st.session_state.current_page = page_key
                st.rerun()

        st.divider()

        # Quick stats
        quizzes = [r for r in db_records if r.get("type") == "QUIZ" and r.get("active", True)]
        scores = [r for r in db_records if r.get("type") == "USER_SCORE"]
        sessions = [r for r in db_records if r.get("type") == "SESSION"]

        st.markdown("**Quick Stats**")
        st.caption(f"📚 Quizzes: {len(quizzes)}")
        st.caption(f"🎮 Sessions: {len(sessions)}")
        st.caption(f"👥 Attempts: {len(scores)}")

        st.divider()

        # Upload JSON to populate DB
        with st.expander("📥 Import DB Records"):
            uploaded = st.file_uploader("Upload JSON records", type="json")
            if uploaded:
                try:
                    data = json.load(uploaded)
                    if isinstance(data, list):
                        st.session_state.db_records = data
                        st.success(f"✅ Loaded {len(data)} records")
                        st.rerun()
                    else:
                        st.error("Expected JSON array")
                except Exception as e:
                    st.error(f"Error: {e}")

        if st.button("🚪 Sign Out", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

        st.caption(f"v1.0.0 · Demo Mode")

    # ── Page Routing ────────────────────────────────────────────────────────────
    page = st.session_state.current_page

    if page == "home":
        render_home(db_records)
    elif page == "creator":
        from admin_panel import quiz_creator
        quiz_creator.render()
    elif page == "editor":
        from admin_panel import quiz_editor
        quiz_editor.render(db_records)
    elif page == "analytics":
        from admin_panel import analytics
        analytics.render(db_records)
    elif page == "scores":
        render_scores(db_records)
    elif page == "logs":
        render_logs(db_records)


# ── Home Page ──────────────────────────────────────────────────────────────────
def render_home(db_records):
    st.markdown("## 🏠 Dashboard Home")
    st.caption("Welcome to the Telegram Quiz Platform Admin Panel")

    quizzes = [r for r in db_records if r.get("type") == "QUIZ" and r.get("active", True)]
    scores = [r for r in db_records if r.get("type") == "USER_SCORE"]
    sessions = [r for r in db_records if r.get("type") == "SESSION"]
    logs = [r for r in db_records if r.get("type") == "LOG"]

    # Hero metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📚 Quizzes", len(quizzes), "+2 this week")
    c2.metric("🎮 Sessions", len(sessions), "+3 this week")
    c3.metric("👥 Total Plays", len(scores), f"+{len(scores)} today")
    c4.metric("🙋 Players", len(set(s.get("user_id") for s in scores)))
    avg = sum(s.get("score", 0) for s in scores) / len(scores) if scores else 0
    c5.metric("📈 Avg Score", f"{avg:.1f}%")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📚 Recent Quizzes")
        for q in quizzes[-5:][::-1]:
            with st.container():
                st.markdown(f"**{q.get('title', 'Untitled')}**")
                c1, c2, c3 = st.columns(3)
                c1.caption(f"🆔 {q.get('id', '?')[:20]}")
                c2.caption(f"❓ {q.get('questions', 0)} questions")
                c3.caption(f"⏱ {q.get('time_per_question', 30)}s/q")
                st.divider()

    with col2:
        st.markdown("### 🏆 Top Players")
        best = {}
        for s in scores:
            uid = s.get("user_id")
            sc = s.get("score", 0)
            if uid not in best or sc > best[uid].get("score", 0):
                best[uid] = s

        top = sorted(best.values(), key=lambda x: x.get("score", 0), reverse=True)[:5]
        rank_emojis = ["🥇", "🥈", "🥉", "4.", "5."]
        for i, u in enumerate(top):
            name = u.get("username") or u.get("first_name", "?")
            score = u.get("score", 0)
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"{rank_emojis[i]} **{name}**")
            c2.markdown(f"**{score:.0f}%**")

    st.divider()

    # Recent activity
    st.markdown("### 📋 Recent Activity")
    recent_logs = [l for l in logs if l.get("level") in ("INFO", "WARNING", "ERROR")][-8:]
    level_icons = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "🔴"}
    for log in reversed(recent_logs):
        icon = level_icons.get(log.get("level", "INFO"), "ℹ️")
        ts = log.get("timestamp", "")[:16].replace("T", " ")
        st.caption(f"{icon} `{ts}` — {log.get('message', '')}")


# ── Scores Page ────────────────────────────────────────────────────────────────
def render_scores(db_records):
    st.markdown("## 🏆 User Scores")
    st.caption("All participant scores across quiz sessions.")

    scores = [r for r in db_records if r.get("type") == "USER_SCORE"]
    quizzes = {q["id"]: q for q in db_records if q.get("type") == "QUIZ"}

    if not scores:
        st.info("No scores recorded yet.")
        return

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        quiz_filter = st.selectbox(
            "Filter by Quiz",
            ["All"] + list(set(s.get("quiz_id", "") for s in scores)),
            format_func=lambda x: "All Quizzes" if x == "All" else quizzes.get(x, {}).get("title", x)
        )
    with col2:
        sort_by = st.selectbox("Sort by", ["Score (High→Low)", "Score (Low→High)", "Name A→Z"])

    # Apply filters
    filtered = scores if quiz_filter == "All" else [s for s in scores if s.get("quiz_id") == quiz_filter]

    sort_map = {
        "Score (High→Low)": lambda x: -x.get("score", 0),
        "Score (Low→High)": lambda x: x.get("score", 0),
        "Name A→Z": lambda x: (x.get("username") or x.get("first_name", "")).lower()
    }
    filtered = sorted(filtered, key=sort_map[sort_by])

    st.markdown(f"**{len(filtered)} records**")
    st.divider()

    # Table display
    for s in filtered:
        col1, col2, col3, col4, col5 = st.columns([2, 2, 1.5, 1.5, 2])
        with col1:
            name = s.get("username") or s.get("first_name", "?")
            st.markdown(f"**{name}**")
            st.caption(f"ID: {s.get('user_id', '?')}")
        with col2:
            qid = s.get("quiz_id", "?")
            qtitle = quizzes.get(qid, {}).get("title", qid[:20])
            st.markdown(f"📚 {qtitle[:25]}")
        with col3:
            correct = s.get("correct", 0)
            total = s.get("total", 0)
            st.markdown(f"✅ {correct}/{total}")
        with col4:
            score = s.get("score", 0)
            color = "green" if score >= 60 else "orange" if score >= 40 else "red"
            st.markdown(f"**:{color}[{score:.0f}%]**")
        with col5:
            ts = s.get("recorded_at", "")[:16].replace("T", " ")
            st.caption(ts)
        st.divider()

    # Export
    import csv, io
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["username", "first_name", "user_id",
                                                  "quiz_id", "correct", "total", "score"])
    writer.writeheader()
    for s in filtered:
        writer.writerow({k: s.get(k, "") for k in ["username", "first_name", "user_id",
                                                     "quiz_id", "correct", "total", "score"]})
    st.download_button("📥 Export as CSV", output.getvalue(),
                       "scores_export.csv", "text/csv", use_container_width=True)


# ── Logs Page ──────────────────────────────────────────────────────────────────
def render_logs(db_records):
    st.markdown("## 📋 System Logs")
    st.caption("Bot activity and system event logs.")

    logs = [r for r in db_records if r.get("type") == "LOG"]

    if not logs:
        st.info("No logs available.")
        return

    level_filter = st.multiselect(
        "Filter by Level",
        ["INFO", "WARNING", "ERROR"],
        default=["INFO", "WARNING", "ERROR"]
    )

    filtered_logs = [l for l in logs if l.get("level", "INFO") in level_filter]
    filtered_logs = list(reversed(filtered_logs))

    st.markdown(f"**{len(filtered_logs)} log entries**")
    st.divider()

    level_colors = {"INFO": "blue", "WARNING": "orange", "ERROR": "red"}
    level_icons = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "🔴"}

    for log in filtered_logs:
        level = log.get("level", "INFO")
        icon = level_icons.get(level, "ℹ️")
        color = level_colors.get(level, "blue")
        ts = log.get("timestamp", "")[:19].replace("T", " ")
        msg = log.get("message", "")
        ctx = log.get("context", {})

        col1, col2, col3 = st.columns([1, 5, 1])
        with col1:
            st.markdown(f":{color}[**{icon} {level}**]")
        with col2:
            st.markdown(msg)
            if ctx:
                st.caption(str(ctx))
        with col3:
            st.caption(ts)
        st.divider()


# ── Entry Point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()

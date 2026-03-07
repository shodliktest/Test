# 🎯 Telegram Quiz Platform

A production-level Telegram quiz system similar to @QuizBot, featuring a full-featured bot and a Streamlit admin panel.

---

## 🏗️ Architecture

```
telegram_quiz_platform/
├── bot/
│   ├── bot.py            # Main bot entry point + polling
│   ├── handlers.py       # All Telegram command & callback handlers
│   ├── quiz_engine.py    # Core quiz session state machine
│   ├── leaderboard.py    # Score aggregation & formatting
│   └── group_manager.py  # Group permission detection
│
├── admin_panel/
│   ├── app.py            # Streamlit dashboard (main entry)
│   ├── quiz_creator.py   # Visual quiz builder page
│   ├── quiz_editor.py    # Quiz editing & deletion page
│   └── analytics.py      # Statistics & reporting page
│
├── database/
│   ├── telegram_db.py    # Primary DB (Telegram group messages)
│   └── firebase_cache.py # Optional Firestore cache
│
├── services/
│   └── quiz_service.py   # Quiz CRUD & lifecycle business logic
│
├── utils/
│   ├── config.py         # Environment-based config
│   ├── helpers.py        # Utilities, record builders, formatters
│   └── json_parser.py    # Telegram message JSON parser
│
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone <repo>
cd telegram_quiz_platform
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required variables:
| Variable | Description |
|---|---|
| `BOT_TOKEN` | From @BotFather |
| `DB_GROUP_ID` | Private Telegram group ID (negative number) |
| `ADMIN_IDS` | Comma-separated Telegram user IDs |
| `ADMIN_USERNAME` | Streamlit dashboard login |
| `ADMIN_PASSWORD` | Streamlit dashboard password |

### 3. Set Up Telegram DB Group

1. Create a **private Telegram group**
2. Add your bot as **administrator**
3. Get the group chat ID (use @userinfobot or check bot logs)
4. Set `DB_GROUP_ID` to that value

### 4. Start the Bot

```bash
python -m bot.bot
# or
cd telegram_quiz_platform && python bot/bot.py
```

### 5. Start the Admin Panel

```bash
streamlit run admin_panel/app.py --server.port 8501
```

Access at: http://localhost:8501

---

## 🤖 Bot Commands

| Command | Who | Description |
|---|---|---|
| `/start` | Everyone | Welcome message |
| `/help` | Everyone | Show all commands |
| `/quiz_list` | Everyone | Browse available quizzes |
| `/quiz_start <id>` | Admins only | Start a quiz in this group |
| `/quiz_stop` | Admins only | Stop the running quiz |
| `/leaderboard` | Everyone | Global top scores |
| `/my_score` | Everyone | Personal score history |
| `/quiz_history` | Everyone | Recent quiz sessions |

---

## 🗄️ Database Design

The platform uses a **private Telegram group as its primary database**. All data is stored as structured JSON messages.

### Record Types

```json
// QUIZ record
{ "type": "QUIZ", "id": "quiz_...", "title": "...", "questions": 10 }

// QUESTION record
{ "type": "QUESTION", "quiz_id": "quiz_...", "index": 0, "text": "...", "options": [...] }

// SESSION record
{ "type": "SESSION", "id": "session_...", "quiz_id": "...", "group_id": -100... }

// USER_SCORE record
{ "type": "USER_SCORE", "session_id": "...", "user_id": 123, "score": 80.0 }

// RESULT aggregate
{ "type": "RESULT", "session_id": "...", "participants": 25, "avg_score": 72.5 }

// LOG record
{ "type": "LOG", "level": "INFO", "message": "...", "timestamp": "..." }
```

**Why Telegram as DB?**
- Zero external database costs
- No Firebase quota limits
- Persistent, auditable history
- Simple backup (export chat history)

---

## ❓ Question Types

| Type | Description |
|---|---|
| `multiple_choice` | 4 option buttons (A/B/C/D) |
| `true_false` | True / False buttons |
| `fill_in_blank` | Text input answer |
| `image` | Question with image URL |

---

## 🛡️ Anti-Cheat System

- **One answer per user** — duplicate answers silently rejected
- **Timer lock** — answers locked after countdown expires
- **Session ID validation** — old question callbacks rejected
- **Question index guard** — answers for wrong question index ignored
- **Spam protection** — group manager can restrict spammers

---

## 🏆 Leaderboard System

- **Live session leaderboard** — shown after quiz ends
- **All-time per-quiz leaderboard** — `/leaderboard` command
- **Global leaderboard** — across all quizzes
- **Personal history** — `/my_score` shows individual stats

---

## 🖥️ Admin Panel Pages

| Page | Description |
|---|---|
| 🏠 Home | Overview metrics, recent activity, top players |
| ✏️ Quiz Creator | Visual quiz builder with JSON preview |
| 📝 Quiz Editor | Edit metadata, view/manage questions |
| 📊 Analytics | Score distribution, session history, export |
| 🏆 User Scores | Filterable score table with CSV export |
| 📋 System Logs | Bot activity log viewer |

---

## 🔧 Configuration Reference

```python
# Quiz behavior
DEFAULT_QUESTION_TIMEOUT = 30   # seconds per question
MAX_QUESTIONS_PER_QUIZ = 50     # upper limit
LEADERBOARD_TOP_N = 10          # positions shown

# Anti-cheat
ANSWER_LOCK_BUFFER = 2          # extra seconds after timer
```

---

## 📈 Scaling Notes

- **In-memory session state** per group — supports hundreds of concurrent groups
- **Telegram DB cache** — cached in memory, refreshed on new messages
- **Firebase optional** — only for cross-process sharing if needed
- **Stateless handlers** — each handler gets fresh services injected
- For very large deployments, replace in-memory cache with Redis

---

## 🔌 Firebase Setup (Optional)

If you want cross-process caching:

1. Create a Firebase project at console.firebase.google.com
2. Enable Firestore
3. Download service account JSON
4. Set `FIREBASE_CREDENTIALS_PATH` and `FIREBASE_PROJECT_ID` in `.env`

Firebase is used **only** for:
- Quiz list caching (reduce Telegram API calls)
- Active session persistence across restarts
- User best-score cache for fast leaderboards

---

## 📝 License

MIT License — Free to use, modify, and distribute.

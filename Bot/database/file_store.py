"""
File Store — JSON fayllar orqali saqlash.

Fayllar:
  data/quizzes.json        ← FAQAT test ID lari (index)
  data/users.json          ← FAQAT user ID + ism (index)
  data/quiz_{id}.json      ← to'liq test + savollar (lazy)
  data/results.json        ← yakuniy natijalar

Startup da yuklanadigan:  quizzes.json, users.json  (kichik)
Kerak bo'lganda yuklanadigan: quiz_{id}.json
"""
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _get_data_dir() -> Path:
    if os.path.exists("/mount/src"):
        d = Path("/tmp/quiz_data")
    else:
        d = Path("./data")
    d.mkdir(parents=True, exist_ok=True)
    return d


DATA_DIR     = _get_data_dir()
INDEX_FILE   = DATA_DIR / "quizzes.json"   # faqat ID lar
USERS_FILE   = DATA_DIR / "users.json"     # faqat user ID + ism
RESULTS_FILE = DATA_DIR / "results.json"   # natijalar


def _write(path: Path, data) -> bool:
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return True
    except Exception as e:
        logger.error(f"❌ Yozish xatosi {path.name}: {e}")
        return False


def _read(path: Path, default=None):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"❌ O'qish xatosi {path.name}: {e}")
    return default


# ════════════════════════════════════════════════════
# QUIZ INDEX — quizzes.json (faqat ID lar)
# ════════════════════════════════════════════════════

def load_quiz_index() -> List[str]:
    """Startup da yuklanadi — faqat ID lar ro'yxati."""
    data = _read(INDEX_FILE, {"ids": []})
    return data.get("ids", [])


def add_to_index(quiz_id: str) -> bool:
    """Yangi test ID sini indexga qo'shadi."""
    data = _read(INDEX_FILE, {"ids": []})
    if quiz_id not in data["ids"]:
        data["ids"].append(quiz_id)
        return _write(INDEX_FILE, data)
    return True


def remove_from_index(quiz_id: str) -> bool:
    """Test ID sini indexdan o'chiradi."""
    data = _read(INDEX_FILE, {"ids": []})
    if quiz_id in data["ids"]:
        data["ids"].remove(quiz_id)
        return _write(INDEX_FILE, data)
    return True


# ════════════════════════════════════════════════════
# QUIZ FAYL — quiz_{id}.json (lazy yuklanadi)
# ════════════════════════════════════════════════════

def save_quiz_file(quiz_id: str, quiz_data: dict) -> bool:
    """To'liq testni alohida faylga yozadi."""
    path = DATA_DIR / f"{quiz_id}.json"
    ok = _write(path, quiz_data)
    if ok:
        logger.info(f"💾 {quiz_id}.json saqlandi")
    return ok


def load_quiz_file(quiz_id: str) -> Optional[dict]:
    """
    Kerak bo'lganda alohida fayldan yuklanadi.
    Startup da CHAQIRILMAYDI.
    """
    path = DATA_DIR / f"{quiz_id}.json"
    data = _read(path)
    if data:
        logger.info(f"📂 {quiz_id}.json yuklandi")
    else:
        logger.warning(f"⚠️ {quiz_id}.json topilmadi")
    return data


def delete_quiz_file(quiz_id: str):
    """Test faylini o'chiradi."""
    path = DATA_DIR / f"{quiz_id}.json"
    try:
        if path.exists():
            path.unlink()
            logger.info(f"🗑️ {quiz_id}.json o'chirildi")
    except Exception as e:
        logger.error(f"❌ O'chirish xatosi: {e}")


def quiz_file_exists(quiz_id: str) -> bool:
    return (DATA_DIR / f"{quiz_id}.json").exists()


# ════════════════════════════════════════════════════
# USERS — users.json (faqat ID + ism)
# ════════════════════════════════════════════════════

def load_users() -> Dict[str, str]:
    """Startup da yuklanadi — {user_id: first_name}."""
    return _read(USERS_FILE, {})


def save_user(user_id: int, first_name: str, username: str = "") -> bool:
    """Foydalanuvchini users.json ga qo'shadi/yangilaydi."""
    users = _read(USERS_FILE, {})
    key   = str(user_id)
    name  = username or first_name or "O'quvchi"
    if users.get(key) != name:
        users[key] = name
        return _write(USERS_FILE, users)
    return True


# ════════════════════════════════════════════════════
# RESULTS — results.json
# ════════════════════════════════════════════════════

def save_result(session_id: str, result_data: dict) -> bool:
    all_results = _read(RESULTS_FILE, {})
    all_results[session_id] = result_data
    ok = _write(RESULTS_FILE, all_results)
    if ok:
        logger.info(f"💾 Natija saqlandi: {session_id}")
    return ok


def load_results() -> dict:
    return _read(RESULTS_FILE, {})


# ════════════════════════════════════════════════════
# FAYL MA'LUMOTLARI
# ════════════════════════════════════════════════════

def file_info() -> dict:
    ids = load_quiz_index()
    quiz_sizes = sum(
        (DATA_DIR / f"{qid}.json").stat().st_size
        for qid in ids if (DATA_DIR / f"{qid}.json").exists()
    )
    return {
        "data_dir":   str(DATA_DIR),
        "quiz_count": len(ids),
        "quiz_ids":   ids,
        "quizzes_kb": round(quiz_sizes / 1024, 1),
        "results_kb": round(RESULTS_FILE.stat().st_size / 1024, 1)
                      if RESULTS_FILE.exists() else 0,
        "users_count": len(load_users()),
    }

# Eski import uchun alias
get_all_quiz_ids = load_quiz_index



# ════════════════════════════════════════════════════
# ACTIVE SESSIONS — restart da tiklash uchun
# ════════════════════════════════════════════════════

ACTIVE_SESSIONS_FILE = DATA_DIR / "active_sessions.json"

def save_active_session(group_id: int, session_data: dict) -> bool:
    """Aktiv sessiyani faylga saqlaydi (restart da tiklash uchun)."""
    all_sessions = _read(ACTIVE_SESSIONS_FILE, {})
    all_sessions[str(group_id)] = session_data
    return _write(ACTIVE_SESSIONS_FILE, all_sessions)

def load_active_sessions() -> dict:
    """Barcha aktiv sessiyalarni yuklaydi."""
    return _read(ACTIVE_SESSIONS_FILE, {})

def delete_active_session(group_id: int):
    """Sessiya tugagach fayldan o'chiradi."""
    all_sessions = _read(ACTIVE_SESSIONS_FILE, {})
    key = str(group_id)
    if key in all_sessions:
        del all_sessions[key]
        _write(ACTIVE_SESSIONS_FILE, all_sessions)

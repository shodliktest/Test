"""
RAM Store — Faqat faol sessiyalar uchun.

Startup da yuklanadigan:
  - quiz_ids: set  ← quizzes.json dan
  - users: dict    ← users.json dan

Sessiya boshida yuklanadigan:
  - active_quizzes[quiz_id] ← quiz_{id}.json dan

Sessiya tugagach o'chiriladigan:
  - active_quizzes[quiz_id]
  - session_scores[session_id]
"""
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


class RAMStore:
    def __init__(self):
        # Startup da yuklanadi
        self.quiz_ids: List[str] = []          # quizzes.json dan
        self.users:    Dict[str, str] = {}     # users.json dan {uid: name}

        # Lazy — faqat sessiya boshida yuklanadi
        self.active_quizzes: Dict[str, dict] = {}

        # Sessiya davomida
        self.sessions:       Dict[str, dict] = {}
        self.session_scores: Dict[str, List] = {}

        self.logs: List[dict] = []

    # ── STARTUP ──────────────────────────────────────

    def init_from_files(self, quiz_ids: List[str], users: Dict[str, str]):
        """Startup da quizzes.json va users.json dan yuklanadi."""
        self.quiz_ids = list(quiz_ids)
        self.users    = dict(users)
        logger.info(f"✅ RAM init: {len(quiz_ids)} test ID, {len(users)} user")

    # ── QUIZ INDEX ───────────────────────────────────

    def has_quiz(self, quiz_id: str) -> bool:
        return quiz_id in self.quiz_ids

    def add_quiz_id(self, quiz_id: str):
        if quiz_id not in self.quiz_ids:
            self.quiz_ids.append(quiz_id)

    def remove_quiz_id(self, quiz_id: str):
        if quiz_id in self.quiz_ids:
            self.quiz_ids.remove(quiz_id)

    # ── LAZY QUIZ LOAD ───────────────────────────────

    def load_quiz(self, quiz_data: dict):
        """quiz_{id}.json dan o'qib RAMga yuklaydi."""
        qid = quiz_data.get("id")
        if qid:
            self.active_quizzes[qid] = quiz_data
            logger.info(f"📥 RAM: {qid} yuklandi")

    def get_quiz(self, quiz_id: str) -> Optional[dict]:
        return self.active_quizzes.get(quiz_id)

    def unload_quiz(self, quiz_id: str):
        """Sessiya tugagach RAMdan o'chiradi."""
        if quiz_id in self.active_quizzes:
            del self.active_quizzes[quiz_id]
            logger.info(f"🗑️ RAM: {quiz_id} o'chirildi")

    # ── USERS ────────────────────────────────────────

    def get_user_name(self, user_id: int) -> str:
        return self.users.get(str(user_id), "O'quvchi")

    def update_user(self, user_id: int, name: str):
        self.users[str(user_id)] = name

    # ── SESSION ──────────────────────────────────────

    def start_session(self, session_id: str, quiz_id: str, quiz_title: str,
                      group_id: int, group_title: str, started_by: int) -> dict:
        rec = {
            "id": session_id, "quiz_id": quiz_id,
            "quiz_title": quiz_title, "group_id": group_id,
            "group_title": group_title, "started_by": started_by,
            "started_at": _now(), "status": "active",
        }
        self.sessions[session_id]      = rec
        self.session_scores[session_id] = []
        return rec

    def end_session(self, session_id: str):
        s = self.sessions.get(session_id)
        if s:
            s["status"]   = "completed"
            s["ended_at"] = _now()

    def get_session(self, session_id: str) -> Optional[dict]:
        return self.sessions.get(session_id)

    def get_sessions(self) -> List[dict]:
        return list(self.sessions.values())

    # ── SCORES ───────────────────────────────────────

    def update_scores(self, session_id: str, scores: List[dict]):
        self.session_scores[session_id] = scores

    def get_scores(self, session_id: str) -> List[dict]:
        return self.session_scores.get(session_id, [])

    def clear_session_progress(self, session_id: str):
        """
        Natijalar e'lon qilinganidan keyin tozalash:
        - Sessiya uchun yuklanган quiz RAMdan o'chiriladi
        - Sessiya ballari o'chiriladi
        """
        quiz_id = self.sessions.get(session_id, {}).get("quiz_id")
        if quiz_id:
            self.unload_quiz(quiz_id)
        if session_id in self.session_scores:
            del self.session_scores[session_id]
        logger.info(f"🧹 RAM tozalandi: session={session_id}")

    # ── LOGS ─────────────────────────────────────────

    def add_log(self, level: str, msg: str):
        self.logs.append({"level": level, "message": msg, "time": _now()})
        if len(self.logs) > 300:
            self.logs = self.logs[-250:]

    def get_logs(self, limit=50) -> List[dict]:
        return self.logs[-limit:]

    def stats(self) -> dict:
        return {
            "quiz_ids_count":   len(self.quiz_ids),
            "active_quizzes":   len(self.active_quizzes),
            "users_count":      len(self.users),
            "sessions":         len(self.sessions),
            "active_sessions":  sum(
                1 for s in self.sessions.values() if s.get("status") == "active"
            ),
        }


ram = RAMStore()

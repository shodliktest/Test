"""
RAM Store — Faqat FAOL sessiyalar uchun.

Arxitektura:
  - Testlar faylda saqlanadi, sessiya boshida RAMga yuklanadi
  - Sessiya tugagach test RAM dan o'chiriladi
  - Natijalar sessiya davomida RAM da saqlanadi
  - Test tugagach natijalar e'lon qilinib RAM dan tozalanadi
  - Sessiya progress (scores) tozalanadi
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


class RAMStore:
    def __init__(self):
        # Faol sessiyalar uchun testlar: quiz_id -> quiz_dict
        # Sessiya tugagach o'chiriladi
        self.active_quizzes: Dict[str, dict] = {}

        # Sessiyalar: session_id -> session_dict
        self.sessions: Dict[str, dict] = {}

        # Sessiya ballari: session_id -> [user_score, ...]
        # Sessiya tugab natijalar e'lon qilinganidan keyin tozalanadi
        self.session_scores: Dict[str, List] = {}

        # Logs
        self.logs: List[dict] = []

    # ════════════════════════════════════════════════
    # QUIZ — faqat faol sessiya uchun RAM da
    # ════════════════════════════════════════════════

    def load_quiz_to_ram(self, quiz_data: dict):
        """Fayldan o'qilgan testni RAM ga yuklaydi."""
        qid = quiz_data.get("id")
        if qid:
            self.active_quizzes[qid] = quiz_data
            logger.info(f"📥 RAM: quiz yuklandi {qid}")

    def get_quiz(self, quiz_id: str) -> Optional[dict]:
        return self.active_quizzes.get(quiz_id)

    def unload_quiz(self, quiz_id: str):
        """Sessiya tugagach testni RAM dan o'chiradi."""
        if quiz_id in self.active_quizzes:
            del self.active_quizzes[quiz_id]
            logger.info(f"🗑️ RAM: quiz o'chirildi {quiz_id}")

    # ════════════════════════════════════════════════
    # SESSION
    # ════════════════════════════════════════════════

    def start_session(self, session_id: str, quiz_id: str, quiz_title: str,
                      group_id: int, group_title: str, started_by: int) -> dict:
        rec = {
            "id": session_id, "quiz_id": quiz_id,
            "quiz_title": quiz_title, "group_id": group_id,
            "group_title": group_title, "started_by": started_by,
            "started_at": _now(), "status": "active",
        }
        self.sessions[session_id] = rec
        self.session_scores[session_id] = []
        return rec

    def end_session(self, session_id: str):
        s = self.sessions.get(session_id)
        if s:
            s["status"] = "completed"
            s["ended_at"] = _now()

    def get_session(self, session_id: str) -> Optional[dict]:
        return self.sessions.get(session_id)

    # ════════════════════════════════════════════════
    # SCORES — sessiya davomida RAM da
    # ════════════════════════════════════════════════

    def update_scores(self, session_id: str, scores: List[dict]):
        """Sessiya ballarini yangilaydi."""
        self.session_scores[session_id] = scores

    def get_scores(self, session_id: str) -> List[dict]:
        return self.session_scores.get(session_id, [])

    def clear_session_progress(self, session_id: str):
        """
        Natijalar e'lon qilinganidan keyin:
        - session_scores tozalanadi (RAM bo'shaydi)
        - Test RAM dan o'chiriladi
        """
        quiz_id = self.sessions.get(session_id, {}).get("quiz_id")
        if quiz_id:
            self.unload_quiz(quiz_id)
        if session_id in self.session_scores:
            del self.session_scores[session_id]
        logger.info(f"🧹 RAM tozalandi: session={session_id}")

    # ════════════════════════════════════════════════
    # LOGS
    # ════════════════════════════════════════════════

    def add_log(self, level: str, msg: str, ctx: dict = None):
        self.logs.append({
            "level": level, "message": msg,
            "context": ctx or {}, "timestamp": _now()
        })
        if len(self.logs) > 500:
            self.logs = self.logs[-400:]

    def get_logs(self, limit=100) -> List[dict]:
        return self.logs[-limit:]

    def stats(self) -> dict:
        return {
            "active_quizzes":  len(self.active_quizzes),
            "sessions":        len(self.sessions),
            "active_sessions": sum(
                1 for s in self.sessions.values() if s.get("status") == "active"
            ),
            "pending_scores":  sum(len(v) for v in self.session_scores.values()),
        }


# Global singleton
ram = RAMStore()

"""
Quiz Service.

Startup:
  startup_load() — quizzes.json + users.json → RAM

Test yaratish:
  create_quiz() → quiz_{id}.json + quizzes.json index → RAM id

Sessiya boshlash:
  get_quiz_with_questions() → quiz_{id}.json → RAM
  record_session_start()    → RAM sessiya

Test tugash:
  record_session_results()  → results.json
                             → RAM tozalash (quiz + scores)
"""
import logging
from typing import Dict, List, Optional, Tuple

from database.ram_store import ram
from database import file_store as fs
from utils.helpers import generate_id, now_iso

logger = logging.getLogger(__name__)


class QuizService:

    def __init__(self):
        self.ram = ram  # global singleton reference

    # ════════════════════════════════════════════════
    # STARTUP — faqat index va userlar
    # ════════════════════════════════════════════════

    def startup_load(self):
        """
        Bot ishga tushganda chaqiriladi.
        Faqat quizzes.json (ID lar) va users.json yuklanadi.
        Test fayllari yuklanmaydi — lazy.
        """
        quiz_ids = fs.load_quiz_index()
        users    = fs.load_users()
        ram.init_from_files(quiz_ids, users)
        logger.info(
            f"🚀 Startup yuklandi: "
            f"{len(quiz_ids)} test ID, {len(users)} user"
        )

    # ════════════════════════════════════════════════
    # TEST YARATISH
    # ════════════════════════════════════════════════

    async def create_quiz(self, title: str, description: str,
                           created_by: str, questions: List[Dict],
                           time_per_question: int = 30) -> Tuple[str, bool]:
        quiz_id   = generate_id("quiz")
        quiz_data = {
            "id":                quiz_id,
            "title":             title,
            "description":       description,
            "created_by":        created_by,
            "time_per_question": time_per_question,
            "question_count":    len(questions),
            "questions":         questions,
            "active":            True,
            "created_at":        now_iso(),
        }
        # Faylga yozish
        ok = fs.save_quiz_file(quiz_id, quiz_data)
        if ok:
            # Indexga qo'shish
            fs.add_to_index(quiz_id)
            ram.add_quiz_id(quiz_id)
        ram.add_log("INFO", f"Quiz yaratildi: {quiz_id} '{title}'")
        return quiz_id, ok

    # ════════════════════════════════════════════════
    # TEST O'QISH
    # ════════════════════════════════════════════════

    def list_quizzes(self) -> List[Dict]:
        """
        Barcha test meta ro'yxati.
        ID dan faylni o'qiydi — questions yo'q, faqat meta.
        """
        result = []
        for qid in ram.quiz_ids:
            data = fs.load_quiz_file(qid)
            if data and data.get("active", True):
                # Savollarni olib tashlash — list uchun kerak emas
                meta = {k: v for k, v in data.items() if k != "questions"}
                result.append(meta)
        return result

    def get_quiz_with_questions(self, quiz_id: str) -> Optional[Dict]:
        """
        To'liq test (meta + questions).
        Avval RAM dan, yo'q bo'lsa fayldan yuklanadi.
        """
        if not ram.has_quiz(quiz_id):
            return None  # Index da yo'q

        # RAM da bormi?
        cached = ram.get_quiz(quiz_id)
        if cached:
            cached = dict(cached)
            cached["question_list"] = cached.get("questions", [])
            return cached

        # Fayldan yukla → RAM
        data = fs.load_quiz_file(quiz_id)
        if not data:
            return None
        ram.load_quiz(data)
        data = dict(data)
        data["question_list"] = data.get("questions", [])
        return data

    def delete_quiz(self, quiz_id: str) -> bool:
        fs.delete_quiz_file(quiz_id)
        fs.remove_from_index(quiz_id)
        ram.remove_quiz_id(quiz_id)
        ram.unload_quiz(quiz_id)
        ram.add_log("INFO", f"Quiz o'chirildi: {quiz_id}")
        return True

    # ════════════════════════════════════════════════
    # SESSION
    # ════════════════════════════════════════════════

    def record_session_start(self, session_id: str, quiz_id: str,
                              quiz_title: str, group_id: int,
                              group_title: str, started_by: int):
        ram.start_session(
            session_id=session_id, quiz_id=quiz_id,
            quiz_title=quiz_title, group_id=group_id,
            group_title=group_title, started_by=started_by
        )

    # ════════════════════════════════════════════════
    # NATIJALAR
    # ════════════════════════════════════════════════

    async def record_session_results(self, session_id: str, quiz_id: str,
                                      group_id: int, results: List[Dict]) -> bool:
        avg   = sum(r["score"] for r in results) / len(results) if results else 0
        top   = results[0] if results else {}
        result_data = {
            "session_id":   session_id,
            "quiz_id":      quiz_id,
            "quiz_title":   ram.sessions.get(session_id, {}).get("quiz_title", ""),
            "group_id":     group_id,
            "participants": len(results),
            "avg_score":    round(avg, 2),
            "top_scorer":   top.get("username") or top.get("first_name", ""),
            "completed_at": now_iso(),
            "user_scores":  results,
        }
        # Faylga saqlash
        fs.save_result(session_id, result_data)
        ram.end_session(session_id)
        ram.add_log("INFO",
            f"Test yakunlandi: {session_id} | {len(results)} kishi | avg={avg:.1f}%")

        # RAM tozalash: quiz + scores o'chiriladi
        ram.clear_session_progress(session_id)
        return True

    # ════════════════════════════════════════════════
    # USER
    # ════════════════════════════════════════════════

    def register_user(self, user_id: int, first_name: str, username: str = ""):
        """Foydalanuvchini users.json ga yozadi (agar yangi bo'lsa)."""
        name = username or first_name or "O'quvchi"
        ram.update_user(user_id, name)
        fs.save_user(user_id, first_name, username)

    # ════════════════════════════════════════════════
    # SO'ROVLAR
    # ════════════════════════════════════════════════

    def get_user_history(self, user_id: int) -> List[Dict]:
        all_results = fs.load_results()
        history = []
        for r in all_results.values():
            for s in r.get("user_scores", []):
                if s.get("user_id") == user_id:
                    history.append({**s, "quiz_title": r.get("quiz_title", "")})
        return history

    def get_sessions(self) -> List[Dict]:
        return ram.get_sessions()

    def get_logs(self, limit=50) -> List[Dict]:
        return ram.get_logs(limit)

    def get_stats(self) -> Dict:
        return {**ram.stats(), **fs.file_info()}

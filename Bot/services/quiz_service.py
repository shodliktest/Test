"""
Quiz Service — File + RAM arxitekturasi.

  Test yaratish:   RAM + quiz_{id}.json + quizzes.json index
  Sessiya boshlash: quiz_{id}.json → RAM yuklash
  Test davomi:     RAM (tez)
  Test tugashi:    natijalar e'lon → RAM tozalash → result → results.json
"""
import logging
from typing import Dict, List, Optional, Tuple

from database.ram_store import ram
from database import file_store as fs
from utils.helpers import generate_id, now_iso, calculate_score

logger = logging.getLogger(__name__)


class QuizService:
    def __init__(self):
        self.ram = ram

    # ════════════════════════════════════════════════
    # TEST YARATISH — faylga yoziladi
    # ════════════════════════════════════════════════

    async def create_quiz(self, title: str, description: str,
                           created_by: str, questions: List[Dict],
                           time_per_question: int = 30) -> Tuple[str, bool]:
        from datetime import datetime
        quiz_id = generate_id("quiz")
        quiz_data = {
            "id":               quiz_id,
            "title":            title,
            "description":      description,
            "created_by":       created_by,
            "time_per_question": time_per_question,
            "question_count":   len(questions),
            "questions":        questions,
            "active":           True,
            "created_at":       now_iso(),
        }
        ok = fs.save_quiz(quiz_id, quiz_data)
        ram.add_log("INFO", f"Quiz yaratildi: {quiz_id} '{title}' ({len(questions)} savol)")
        return quiz_id, ok

    # ════════════════════════════════════════════════
    # TEST O'QISH — fayldan (lazy)
    # ════════════════════════════════════════════════

    def get_quiz_meta(self, quiz_id: str) -> Optional[Dict]:
        """Faqat meta (questions yo'q) — tez."""
        return fs.load_quiz_meta(quiz_id)

    def get_quiz_with_questions(self, quiz_id: str) -> Optional[Dict]:
        """
        To'liq test (meta + questions).
        Avval RAM dan qidiradi, topilmasa fayldan yuklaydi.
        """
        # RAM da bormi?
        cached = ram.get_quiz(quiz_id)
        if cached:
            cached["question_list"] = cached.get("questions", [])
            return cached

        # Fayldan yukla
        data = fs.load_quiz(quiz_id)
        if not data:
            return None

        # RAM ga yuklash (sessiya boshida kerak bo'ladi)
        ram.load_quiz_to_ram(data)
        data["question_list"] = data.get("questions", [])
        return data

    def list_quizzes(self) -> List[Dict]:
        """Barcha faol testlarning meta ro'yxati."""
        return [m for m in fs.get_all_quizzes_meta() if m.get("active", True)]

    def delete_quiz(self, quiz_id: str) -> bool:
        # Faylni o'chirish
        fs.delete_quiz_file(quiz_id)
        # RAM dan ham
        ram.unload_quiz(quiz_id)
        ram.add_log("INFO", f"Quiz o'chirildi: {quiz_id}")
        return True

    # ════════════════════════════════════════════════
    # SESSIYA
    # ════════════════════════════════════════════════

    def record_session_start(self, session_id: str, quiz_id: str,
                              quiz_title: str, group_id: int,
                              group_title: str, started_by: int):
        ram.start_session(
            session_id=session_id, quiz_id=quiz_id,
            quiz_title=quiz_title, group_id=group_id,
            group_title=group_title, started_by=started_by
        )
        ram.add_log("INFO", f"Sessiya boshlandi: {session_id} | guruh={group_id}")

    # ════════════════════════════════════════════════
    # NATIJALAR — e'lon qilinib RAM tozalanadi
    # ════════════════════════════════════════════════

    async def record_session_results(self, session_id: str, quiz_id: str,
                                      group_id: int, results: List[Dict]) -> bool:
        """
        1. Natijalarni results.json ga saqlaydi
        2. RAM dan session scores + quiz o'chiriladi
        """
        avg_score = sum(r["score"] for r in results) / len(results) if results else 0
        top       = results[0] if results else {}
        top_name  = top.get("username") or top.get("first_name", "Noma'lum")

        result_data = {
            "session_id":   session_id,
            "quiz_id":      quiz_id,
            "quiz_title":   ram.sessions.get(session_id, {}).get("quiz_title", ""),
            "group_id":     group_id,
            "participants": len(results),
            "avg_score":    round(avg_score, 2),
            "top_scorer":   top_name,
            "completed_at": now_iso(),
            "user_scores":  results,
        }

        # Faylga saqlash
        fs.save_result(session_id, result_data)
        ram.end_session(session_id)

        ram.add_log("INFO",
            f"Test yakunlandi: {session_id} | {len(results)} kishi | avg={avg_score:.1f}%")

        # RAM dan progress tozalash (test + scores)
        ram.clear_session_progress(session_id)

        return True

    # ════════════════════════════════════════════════
    # SO'ROVLAR
    # ════════════════════════════════════════════════

    def get_all_results(self) -> Dict:
        return fs.load_results()

    def get_session_results(self, session_id: str) -> Optional[Dict]:
        return fs.load_results().get(session_id)

    def get_user_history(self, user_id: int) -> List[Dict]:
        all_results = fs.load_results()
        history = []
        for r in all_results.values():
            for score in r.get("user_scores", []):
                if score.get("user_id") == user_id:
                    history.append({**score, "quiz_title": r.get("quiz_title", "")})
        return history

    def get_sessions(self) -> List[Dict]:
        return list(ram.sessions.values())

    def get_logs(self, limit=100) -> List[Dict]:
        return ram.get_logs(limit)

    def get_stats(self) -> Dict:
        ram_stats  = ram.stats()
        file_stats = fs.file_info()
        return {**ram_stats, **file_stats}

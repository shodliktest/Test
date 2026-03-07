"""
Quiz Service — RAM store asosida.
Test yaratilganda va tugaganda kanalga JSON yoziladi.
"""
import logging
from typing import Dict, List, Optional, Tuple
from database.ram_store import ram
from utils.helpers import generate_id, now_iso, calculate_score

logger = logging.getLogger(__name__)

# ChannelDB ni lazy ulaymiz (bot ishga tushganda)
_channel_db = None

def set_channel_db(ch):
    global _channel_db
    _channel_db = ch


class QuizService:
    def __init__(self):
        self.ram = ram

    # ── TEST ─────────────────────────────────────────
    async def create_quiz(self, title: str, description: str,
                           created_by: str, questions: List[Dict],
                           time_per_question: int = 30) -> Tuple[str, bool]:
        quiz_id = generate_id("quiz")
        ram.save_quiz(
            quiz_id=quiz_id, title=title, description=description,
            created_by=created_by, time_per_question=time_per_question,
            questions=questions
        )
        ram.add_log("INFO", f"Quiz yaratildi: {quiz_id} '{title}'")
        # Kanalga saqlash
        if _channel_db:
            await _channel_db.save_quiz(quiz_id)
        return quiz_id, True

    def get_quiz(self, quiz_id: str) -> Optional[Dict]:
        return ram.get_quiz(quiz_id)

    def get_quiz_with_questions(self, quiz_id: str) -> Optional[Dict]:
        quiz = ram.get_quiz(quiz_id)
        if not quiz:
            return None
        quiz = dict(quiz)
        quiz["question_list"] = quiz.get("questions", [])
        return quiz

    def list_quizzes(self) -> List[Dict]:
        return ram.get_all_quizzes()

    def delete_quiz(self, quiz_id: str) -> bool:
        ok = ram.delete_quiz(quiz_id)
        if ok:
            ram.add_log("INFO", f"Quiz o'chirildi: {quiz_id}")
        return ok

    # ── SESSIYA ──────────────────────────────────────
    def record_session_start(self, session_id, quiz_id, quiz_title,
                              group_id, group_title, started_by):
        ram.save_session(
            session_id=session_id, quiz_id=quiz_id, quiz_title=quiz_title,
            group_id=group_id, group_title=group_title, started_by=started_by
        )
        ram.add_log("INFO", f"Sessiya boshlandi: {session_id}")

    # ── NATIJALAR — test tugaganda kanalga yoziladi ──
    async def record_session_results(self, session_id: str, quiz_id: str,
                                      group_id: int, results: List[Dict]) -> bool:
        # RAM ga saqlash
        user_scores = [
            {
                "type": "USER_SCORE", "session_id": session_id, "quiz_id": quiz_id,
                "user_id":    r["user_id"],
                "username":   r.get("username", ""),
                "first_name": r.get("first_name", ""),
                "correct":    r["correct"],
                "total":      r["total"],
                "score":      r["score"],
                "recorded_at": now_iso(),
            }
            for r in results
        ]
        ram.save_scores(session_id, user_scores)
        ram.end_session(session_id)

        avg_score = sum(r["score"] for r in results) / len(results) if results else 0
        top       = results[0] if results else {}
        top_name  = top.get("username") or top.get("first_name", "Noma'lum")
        ram.save_result(
            session_id=session_id, quiz_id=quiz_id, group_id=group_id,
            participants=len(results), avg_score=round(avg_score, 2),
            top_scorer=top_name,
        )
        ram.add_log("INFO",
            f"Test yakunlandi: {session_id} | {len(results)} kishi | avg={avg_score:.1f}%")

        # Kanalga saqlash (test tugaganda)
        if _channel_db:
            await _channel_db.save_result(session_id)
        return True

    # ── SO'ROVLAR ────────────────────────────────────
    def get_sessions(self) -> List[Dict]:
        return ram.get_sessions()

    def get_all_scores(self) -> List[Dict]:
        return ram.get_all_scores()

    def get_user_history(self, user_id: int) -> List[Dict]:
        return ram.get_user_history(user_id)

    def get_logs(self, limit=100) -> List[Dict]:
        return ram.get_logs(limit)

    def get_stats(self) -> Dict:
        return ram.stats()

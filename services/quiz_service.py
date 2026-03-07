"""
Quiz Service - Business logic for quiz lifecycle management
"""
import logging
from typing import Dict, List, Optional, Tuple
from utils.helpers import (
    generate_id, build_quiz_record, build_question_record,
    build_session_record, build_result_record, build_user_score_record,
    build_log_record, now_iso
)
from utils.config import config

logger = logging.getLogger(__name__)


class QuizService:
    """Handles quiz CRUD and lifecycle operations."""

    def __init__(self, db):
        self.db = db

    async def create_quiz(self, title: str, description: str,
                           created_by: str, questions: List[Dict],
                           time_per_question: int = 30) -> Tuple[str, bool]:
        """
        Create a new quiz and store all questions.
        Returns (quiz_id, success).
        """
        quiz_id = generate_id("quiz")
        quiz_record = build_quiz_record(
            quiz_id=quiz_id,
            title=title,
            description=description,
            created_by=created_by,
            question_count=len(questions),
            time_per_question=time_per_question
        )

        # Write quiz metadata
        msg_id = await self.db.write_record(quiz_record)
        if not msg_id:
            return quiz_id, False

        # Update cache
        self.db.update_cache(msg_id, self._to_db_format(quiz_record))

        # Write each question
        for i, q in enumerate(questions):
            q_record = build_question_record(
                quiz_id=quiz_id,
                question_index=i,
                question_text=q["text"],
                options=q["options"],
                correct_index=q["correct_index"],
                question_type=q.get("type", "multiple_choice"),
                explanation=q.get("explanation", ""),
                image_url=q.get("image_url", "")
            )
            qmsg_id = await self.db.write_record(q_record)
            if qmsg_id:
                self.db.update_cache(qmsg_id, self._to_db_format(q_record))

        # Log creation
        log = build_log_record("INFO", f"Quiz created: {quiz_id} '{title}' by {created_by}")
        log_id = await self.db.write_record(log)
        if log_id:
            self.db.update_cache(log_id, self._to_db_format(log))

        logger.info(f"Quiz created: {quiz_id}")
        return quiz_id, True

    def _to_db_format(self, record: Dict) -> str:
        """Convert record to DB message format for cache update."""
        import json
        return f"📦 DB_RECORD\n```json\n{json.dumps(record, ensure_ascii=False, indent=2)}\n```"

    async def get_quiz_with_questions(self, quiz_id: str) -> Optional[Dict]:
        """Get a quiz with all its questions."""
        quiz = await self.db.get_quiz(quiz_id)
        if not quiz:
            return None
        questions = await self.db.get_quiz_questions(quiz_id)
        quiz["question_list"] = questions
        return quiz

    async def list_quizzes(self) -> List[Dict]:
        """List all active quizzes."""
        return await self.db.get_all_quizzes()

    async def delete_quiz(self, quiz_id: str) -> bool:
        """Soft delete a quiz."""
        success = await self.db.soft_delete_quiz(quiz_id)
        if success:
            log = build_log_record("INFO", f"Quiz deleted: {quiz_id}")
            log_id = await self.db.write_record(log)
            if log_id:
                self.db.update_cache(log_id, self._to_db_format(log))
        return success

    async def record_session_start(self, session_id: str, quiz_id: str,
                                    quiz_title: str, group_id: int,
                                    group_title: str, started_by: int) -> bool:
        """Record that a quiz session has started."""
        record = build_session_record(
            session_id=session_id,
            quiz_id=quiz_id,
            quiz_title=quiz_title,
            group_id=group_id,
            group_title=group_title,
            started_by=started_by
        )
        msg_id = await self.db.write_record(record)
        if msg_id:
            self.db.update_cache(msg_id, self._to_db_format(record))
        return msg_id is not None

    async def record_session_results(self, session_id: str, quiz_id: str,
                                      group_id: int, results: List[Dict]) -> bool:
        """Record final session results."""
        if not results:
            return True

        # Write individual user scores
        for result in results:
            score_record = build_user_score_record(
                session_id=session_id,
                quiz_id=quiz_id,
                user_id=result["user_id"],
                username=result.get("username", ""),
                first_name=result.get("first_name", ""),
                correct=result["correct"],
                total=result["total"],
                score=result["score"]
            )
            msg_id = await self.db.write_record(score_record)
            if msg_id:
                self.db.update_cache(msg_id, self._to_db_format(score_record))

        # Write aggregate result
        top = results[0] if results else {}
        top_name = top.get("username") or top.get("first_name", "Unknown")
        avg_score = sum(r["score"] for r in results) / len(results)
        result_record = build_result_record(
            session_id=session_id,
            quiz_id=quiz_id,
            group_id=group_id,
            participants=len(results),
            avg_score=round(avg_score, 2),
            top_scorer=top_name
        )
        msg_id = await self.db.write_record(result_record)
        if msg_id:
            self.db.update_cache(msg_id, self._to_db_format(result_record))

        return True

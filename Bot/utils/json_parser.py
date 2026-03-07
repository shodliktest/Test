"""
JSON Parser - Parses structured records from Telegram group message history
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from utils.helpers import parse_json_from_message

logger = logging.getLogger(__name__)


class TelegramJSONParser:
    """
    Parses structured JSON records stored as Telegram messages.
    The private Telegram group acts as a database.
    """

    VALID_TYPES = {"QUIZ", "QUESTION", "RESULT", "USER_SCORE", "LOG", "SESSION"}

    @staticmethod
    def parse_message(message_text: str) -> Optional[Dict[str, Any]]:
        """Parse a single message into a structured record."""
        record = parse_json_from_message(message_text)
        if not record:
            return None
        if record.get("type") not in TelegramJSONParser.VALID_TYPES:
            return None
        return record

    @staticmethod
    def parse_messages_batch(messages: List[Tuple[int, str]]) -> List[Dict[str, Any]]:
        """
        Parse a batch of (message_id, text) tuples.
        Returns list of valid records.
        """
        records = []
        for msg_id, text in messages:
            record = TelegramJSONParser.parse_message(text)
            if record:
                record["_message_id"] = msg_id
                records.append(record)
        return records

    @staticmethod
    def filter_by_type(records: List[Dict], record_type: str) -> List[Dict]:
        """Filter records by type."""
        return [r for r in records if r.get("type") == record_type]

    @staticmethod
    def get_quiz_by_id(records: List[Dict], quiz_id: str) -> Optional[Dict]:
        """Find a quiz record by ID."""
        quizzes = TelegramJSONParser.filter_by_type(records, "QUIZ")
        for quiz in quizzes:
            if quiz.get("id") == quiz_id:
                return quiz
        return None

    @staticmethod
    def get_questions_for_quiz(records: List[Dict], quiz_id: str) -> List[Dict]:
        """Get all questions for a quiz, sorted by index."""
        questions = TelegramJSONParser.filter_by_type(records, "QUESTION")
        quiz_questions = [q for q in questions if q.get("quiz_id") == quiz_id]
        return sorted(quiz_questions, key=lambda q: q.get("index", 0))

    @staticmethod
    def get_scores_for_session(records: List[Dict], session_id: str) -> List[Dict]:
        """Get all user scores for a session, sorted by score descending."""
        scores = TelegramJSONParser.filter_by_type(records, "USER_SCORE")
        session_scores = [s for s in scores if s.get("session_id") == session_id]
        return sorted(session_scores, key=lambda s: s.get("score", 0), reverse=True)

    @staticmethod
    def get_user_history(records: List[Dict], user_id: int) -> List[Dict]:
        """Get all quiz attempts for a user."""
        scores = TelegramJSONParser.filter_by_type(records, "USER_SCORE")
        return [s for s in scores if s.get("user_id") == user_id]

    @staticmethod
    def get_active_quizzes(records: List[Dict]) -> List[Dict]:
        """Get all active (non-deleted) quizzes."""
        quizzes = TelegramJSONParser.filter_by_type(records, "QUIZ")
        return [q for q in quizzes if q.get("active", True)]

    @staticmethod
    def get_sessions_for_quiz(records: List[Dict], quiz_id: str) -> List[Dict]:
        """Get all sessions for a specific quiz."""
        sessions = TelegramJSONParser.filter_by_type(records, "SESSION")
        return [s for s in sessions if s.get("quiz_id") == quiz_id]

    @staticmethod
    def build_analytics(records: List[Dict], quiz_id: str) -> Dict:
        """Build analytics data for a quiz."""
        sessions = TelegramJSONParser.get_sessions_for_quiz(records, quiz_id)
        all_scores = []
        for session in sessions:
            sid = session.get("id")
            scores = TelegramJSONParser.get_scores_for_session(records, sid)
            all_scores.extend(scores)

        if not all_scores:
            return {
                "total_attempts": 0,
                "unique_participants": 0,
                "avg_score": 0,
                "highest_score": 0,
                "lowest_score": 0,
                "pass_rate": 0
            }

        score_values = [s.get("score", 0) for s in all_scores]
        unique_users = len(set(s.get("user_id") for s in all_scores))
        pass_count = sum(1 for s in score_values if s >= 60)

        return {
            "total_attempts": len(all_scores),
            "unique_participants": unique_users,
            "avg_score": round(sum(score_values) / len(score_values), 2),
            "highest_score": max(score_values),
            "lowest_score": min(score_values),
            "pass_rate": round(pass_count / len(score_values) * 100, 1)
        }

    @staticmethod
    def build_question_difficulty(records: List[Dict], quiz_id: str) -> List[Dict]:
        """Analyze difficulty per question based on answer history."""
        # This would require per-answer records; return question list with placeholders
        questions = TelegramJSONParser.get_questions_for_quiz(records, quiz_id)
        result = []
        for q in questions:
            result.append({
                "index": q.get("index", 0),
                "text": q.get("text", "")[:60] + "...",
                "correct_rate": None  # Would need answer records to compute
            })
        return result

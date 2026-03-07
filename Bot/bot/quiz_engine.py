"""
Quiz Engine - Core logic for running quiz sessions
Manages state, timers, answers, and scoring per session
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from datetime import datetime

from utils.config import config
from utils.helpers import (
    generate_id, build_session_record, build_result_record,
    build_user_score_record, calculate_score, format_leaderboard, now_iso
)

logger = logging.getLogger(__name__)


@dataclass
class UserAnswer:
    user_id: int
    username: str
    first_name: str
    answer_index: int
    is_correct: bool
    answered_at: str = field(default_factory=now_iso)


@dataclass
class QuizSession:
    """Represents an active quiz session in a group."""
    session_id: str
    quiz_id: str
    quiz_title: str
    group_id: int
    group_title: str
    started_by: int
    questions: List[Dict]
    time_per_question: int

    # Runtime state
    current_question_index: int = 0
    is_active: bool = True
    is_question_active: bool = False
    answers_locked: bool = False

    # Per-question tracking
    current_answers: Dict[int, UserAnswer] = field(default_factory=dict)  # user_id -> answer

    # Session-wide tracking
    user_scores: Dict[int, Dict] = field(default_factory=dict)  # user_id -> {correct, total, info}
    participants: Set[int] = field(default_factory=set)

    # Message IDs for editing
    question_message_id: Optional[int] = None
    leaderboard_message_id: Optional[int] = None

    # Timer handle
    _timer_task: Optional[asyncio.Task] = None

    started_at: str = field(default_factory=now_iso)

    @property
    def current_question(self) -> Optional[Dict]:
        if self.current_question_index < len(self.questions):
            return self.questions[self.current_question_index]
        return None

    @property
    def is_last_question(self) -> bool:
        return self.current_question_index >= len(self.questions) - 1

    @property
    def total_questions(self) -> int:
        return len(self.questions)

    def record_answer(self, user_id: int, username: str, first_name: str,
                      answer_index: int) -> Optional[bool]:
        """
        Record a user's answer. Returns True if correct, False if wrong,
        None if already answered or answers locked.
        """
        if self.answers_locked:
            return None
        if user_id in self.current_answers:
            return None  # Already answered

        q = self.current_question
        if not q:
            return None

        is_correct = answer_index == q.get("correct_index", -1)
        self.current_answers[user_id] = UserAnswer(
            user_id=user_id,
            username=username,
            first_name=first_name,
            answer_index=answer_index,
            is_correct=is_correct
        )
        self.participants.add(user_id)

        # Update cumulative scores
        if user_id not in self.user_scores:
            self.user_scores[user_id] = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "correct": 0,
                "total": 0
            }
        self.user_scores[user_id]["total"] += 1
        if is_correct:
            self.user_scores[user_id]["correct"] += 1

        return is_correct

    def lock_answers(self):
        """Lock answers for current question."""
        self.answers_locked = True

    def advance_question(self):
        """Move to next question, reset per-question state."""
        self.current_question_index += 1
        self.current_answers = {}
        self.answers_locked = False
        self.is_question_active = False
        self.question_message_id = None

    def get_leaderboard(self) -> List[Dict]:
        """Get current leaderboard sorted by score."""
        scores = []
        for uid, data in self.user_scores.items():
            correct = data["correct"]
            total = data["total"]
            score = calculate_score(correct, total)
            scores.append({
                "user_id": uid,
                "username": data["username"],
                "first_name": data["first_name"],
                "correct": correct,
                "total": total,
                "score": score
            })
        return sorted(scores, key=lambda x: x["score"], reverse=True)

    def get_final_results(self) -> List[Dict]:
        """Get final results for all participants."""
        results = []
        for uid, data in self.user_scores.items():
            correct = data["correct"]
            total = self.total_questions
            # Ensure total reflects all questions
            score = calculate_score(correct, total)
            results.append({
                "user_id": uid,
                "username": data["username"],
                "first_name": data["first_name"],
                "correct": correct,
                "total": total,
                "score": score
            })
        return sorted(results, key=lambda x: x["score"], reverse=True)

    def cancel_timer(self):
        """Cancel the current question timer."""
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()


class QuizSessionManager:
    """Manages all active quiz sessions across groups."""

    def __init__(self):
        self._sessions: Dict[int, QuizSession] = {}  # group_id -> session

    def create_session(self, quiz_id: str, quiz_title: str,
                       group_id: int, group_title: str,
                       started_by: int, questions: List[Dict],
                       time_per_question: int) -> QuizSession:
        """Create and register a new quiz session."""
        session_id = generate_id("session")
        session = QuizSession(
            session_id=session_id,
            quiz_id=quiz_id,
            quiz_title=quiz_title,
            group_id=group_id,
            group_title=group_title,
            started_by=started_by,
            questions=questions,
            time_per_question=time_per_question
        )
        self._sessions[group_id] = session
        logger.info(f"Session created: {session_id} for group {group_id}")
        return session

    def get_session(self, group_id: int) -> Optional[QuizSession]:
        """Get active session for a group."""
        return self._sessions.get(group_id)

    def end_session(self, group_id: int) -> Optional[QuizSession]:
        """End and remove a session."""
        session = self._sessions.pop(group_id, None)
        if session:
            session.is_active = False
            session.cancel_timer()
            logger.info(f"Session ended: {session.session_id}")
        return session

    def has_active_session(self, group_id: int) -> bool:
        """Check if a group has an active session."""
        return group_id in self._sessions

    def get_all_sessions(self) -> List[QuizSession]:
        """Get all active sessions."""
        return list(self._sessions.values())


# Global session manager instance
session_manager = QuizSessionManager()

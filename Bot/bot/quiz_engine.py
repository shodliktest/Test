"""
Quiz Engine — Telegram Quiz Poll asosida.

Har savol uchun:
  send_poll(type="quiz", open_period=N) — Telegram o'zi timer ko'rsatadi
  poll_answer update — kim to'g'ri javob berganini bot biladi
  open_period tugagach — bot keyingi savolga o'tadi
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from utils.helpers import generate_id, calculate_score, now_iso

logger = logging.getLogger(__name__)


@dataclass
class QuizSession:
    session_id:        str
    quiz_id:           str
    quiz_title:        str
    group_id:          int
    group_title:       str
    started_by:        int
    questions:         List[Dict]
    time_per_question: int

    # Holat
    current_question_index: int  = 0
    is_active:               bool = True

    # Joriy savol poll ma'lumotlari
    current_poll_id:      Optional[str] = None   # Telegram poll_id
    current_poll_msg_id:  Optional[int] = None   # xabar msg_id (stop uchun)

    # Joriy savol javoblari: user_id -> answer_option_ids[0]
    current_answers: Dict[int, Dict] = field(default_factory=dict)

    # Sessiya ballari: user_id -> {correct, info}
    user_scores: Dict[int, Dict] = field(default_factory=dict)

    # Timer task
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

    def record_poll_answer(self, user_id: int, username: str,
                           first_name: str, option_ids: List[int]) -> Optional[bool]:
        """
        Telegram PollAnswer update dan javobni qayd etadi.
        option_ids bo'sh bo'lsa — foydalanuvchi javobini bekor qilgan.
        """
        if not self.is_active:
            return None
        if not option_ids:
            return None  # Javobni bekor qildi
        if user_id in self.current_answers:
            return None  # Allaqachon javob bergan

        q = self.current_question
        if not q:
            return None

        answer_idx  = option_ids[0]
        correct_idx = q.get("correct_index", 0)
        is_correct  = (answer_idx == correct_idx)

        logger.info(
            f"📝 Javob: user={username}({user_id}) "
            f"savol={self.current_question_index} "
            f"tanlov={answer_idx} togri={correct_idx} "
            f"natija={'✅' if is_correct else '❌'}"
        )

        self.current_answers[user_id] = {
            "user_id":    user_id,
            "username":   username,
            "first_name": first_name,
            "answer_idx": answer_idx,
            "is_correct": is_correct,
        }

        # Kumulativ ball
        if user_id not in self.user_scores:
            self.user_scores[user_id] = {
                "user_id":    user_id,
                "username":   username,
                "first_name": first_name,
                "correct":    0,
            }
        if is_correct:
            self.user_scores[user_id]["correct"] += 1

        logger.info(f"📊 Jami: {username} -> {self.user_scores[user_id]['correct']} togri")
        return is_correct

    def advance_question(self):
        self.current_question_index += 1
        self.current_answers  = {}
        self.current_poll_id  = None
        self.current_poll_msg_id = None

    def get_final_results(self) -> List[Dict]:
        results = []
        total_q = self.total_questions
        for uid, d in self.user_scores.items():
            correct = d["correct"]
            score   = calculate_score(correct, total_q)
            results.append({
                "user_id":    uid,
                "username":   d["username"],
                "first_name": d["first_name"],
                "correct":    correct,
                "total":      total_q,
                "score":      score,
            })
        return sorted(results, key=lambda x: x["score"], reverse=True)

    def cancel_timer(self):
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()


class QuizSessionManager:
    def __init__(self):
        self._sessions: Dict[int, QuizSession] = {}   # group_id → session
        self._by_poll:  Dict[str, int]          = {}   # poll_id  → group_id

    def create_session(self, quiz_id, quiz_title, group_id, group_title,
                       started_by, questions, time_per_question) -> QuizSession:
        session_id = generate_id("session")
        session = QuizSession(
            session_id=session_id, quiz_id=quiz_id,
            quiz_title=quiz_title, group_id=group_id,
            group_title=group_title, started_by=started_by,
            questions=questions, time_per_question=time_per_question,
        )
        self._sessions[group_id] = session
        logger.info(f"Sessiya yaratildi: {session_id} | guruh={group_id}")
        return session

    def register_poll(self, poll_id: str, group_id: int):
        """Poll yuborilganda poll_id → group_id bog'laydi."""
        self._by_poll[poll_id] = group_id

    def get_session(self, group_id: int) -> Optional[QuizSession]:
        return self._sessions.get(group_id)

    def get_session_by_poll(self, poll_id: str) -> Optional[QuizSession]:
        group_id = self._by_poll.get(poll_id)
        if group_id:
            return self._sessions.get(group_id)
        return None

    def end_session(self, group_id: int) -> Optional[QuizSession]:
        session = self._sessions.pop(group_id, None)
        if session:
            session.is_active = False
            session.cancel_timer()
            # Poll map dan ham tozalash
            dead = [pid for pid, gid in self._by_poll.items() if gid == group_id]
            for pid in dead:
                del self._by_poll[pid]
        return session

    def has_active_session(self, group_id: int) -> bool:
        return group_id in self._sessions

    def get_all_sessions(self) -> List[QuizSession]:
        return list(self._sessions.values())


session_manager = QuizSessionManager()

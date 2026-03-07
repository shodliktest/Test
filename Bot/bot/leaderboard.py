"""
Leaderboard Service - Manages score aggregation and leaderboard display
"""
import logging
from typing import Dict, List, Optional
from utils.helpers import get_rank_emoji, format_score

logger = logging.getLogger(__name__)


class LeaderboardService:
    """Handles leaderboard computation and formatting."""

    def __init__(self, db):
        self.db = db

    async def get_quiz_leaderboard(self, quiz_id: str, limit: int = 10) -> List[Dict]:
        """Get overall leaderboard for a quiz across all sessions."""
        all_scores = self.db.get_all_scores_from_cache()
        quiz_scores = [s for s in all_scores if s.get("quiz_id") == quiz_id]

        # Best score per user
        best_scores: Dict[int, Dict] = {}
        for score_rec in quiz_scores:
            uid = score_rec.get("user_id")
            score = score_rec.get("score", 0)
            if uid not in best_scores or score > best_scores[uid]["score"]:
                best_scores[uid] = score_rec

        sorted_scores = sorted(best_scores.values(), key=lambda x: x.get("score", 0), reverse=True)
        return sorted_scores[:limit]

    async def get_global_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get global leaderboard across all quizzes."""
        all_scores = self.db.get_all_scores_from_cache()

        # Aggregate by user
        user_totals: Dict[int, Dict] = {}
        for score_rec in all_scores:
            uid = score_rec.get("user_id")
            if uid not in user_totals:
                user_totals[uid] = {
                    "user_id": uid,
                    "username": score_rec.get("username"),
                    "first_name": score_rec.get("first_name", "Unknown"),
                    "total_quizzes": 0,
                    "total_correct": 0,
                    "total_questions": 0,
                    "avg_score": 0
                }
            user_totals[uid]["total_quizzes"] += 1
            user_totals[uid]["total_correct"] += score_rec.get("correct", 0)
            user_totals[uid]["total_questions"] += score_rec.get("total", 0)

        for uid, data in user_totals.items():
            tq = data["total_questions"]
            tc = data["total_correct"]
            data["avg_score"] = round((tc / tq * 100) if tq > 0 else 0, 1)

        sorted_users = sorted(user_totals.values(), key=lambda x: x["avg_score"], reverse=True)
        return sorted_users[:limit]

    def format_session_leaderboard(self, session_results: List[Dict],
                                    quiz_title: str = "") -> str:
        """Format session results as a Telegram message."""
        title = f"🏆 *{quiz_title} — Final Results*\n" if quiz_title else "🏆 *Final Results*\n"
        lines = [title, ""]

        if not session_results:
            lines.append("No participants recorded.")
            return "\n".join(lines)

        for i, entry in enumerate(session_results[:10], 1):
            rank = get_rank_emoji(i)
            name = entry.get("username") or entry.get("first_name", "Player")
            correct = entry.get("correct", 0)
            total = entry.get("total", 0)
            score = entry.get("score", 0)
            lines.append(f"{rank} {name}  —  {score:.0f}pts  ({correct}/{total} ✅)")

        if len(session_results) > 10:
            lines.append(f"\n_...and {len(session_results) - 10} more participants_")

        lines.append(f"\n👥 Total Participants: {len(session_results)}")

        all_scores = [e.get("score", 0) for e in session_results]
        avg = sum(all_scores) / len(all_scores) if all_scores else 0
        lines.append(f"📊 Average Score: {avg:.1f}pts")

        return "\n".join(lines)

    def format_quiz_leaderboard(self, scores: List[Dict], quiz_title: str = "") -> str:
        """Format all-time quiz leaderboard."""
        title = f"🥇 *All-Time: {quiz_title}*\n" if quiz_title else "🥇 *All-Time Leaderboard*\n"
        lines = [title]

        if not scores:
            lines.append("No scores yet!")
            return "\n".join(lines)

        for i, entry in enumerate(scores, 1):
            rank = get_rank_emoji(i)
            name = entry.get("username") or entry.get("first_name", "Player")
            score = entry.get("score", 0)
            correct = entry.get("correct", 0)
            total = entry.get("total", 0)
            lines.append(f"{rank} {name} — {score:.0f}pts ({correct}/{total})")

        return "\n".join(lines)

    def format_global_leaderboard(self, users: List[Dict]) -> str:
        """Format global leaderboard."""
        lines = ["🌍 *Global Leaderboard*\n"]

        if not users:
            lines.append("No data yet!")
            return "\n".join(lines)

        for i, entry in enumerate(users, 1):
            rank = get_rank_emoji(i)
            name = entry.get("username") or entry.get("first_name", "Player")
            avg = entry.get("avg_score", 0)
            quizzes = entry.get("total_quizzes", 0)
            lines.append(f"{rank} {name} — {avg:.0f}% avg ({quizzes} quizzes)")

        return "\n".join(lines)

    def format_my_score(self, user_scores: List[Dict], first_name: str) -> str:
        """Format personal score history."""
        if not user_scores:
            return f"📊 *{first_name}'s Scores*\n\nNo quiz attempts yet\\! Start a quiz to see your scores\\."

        lines = [f"📊 *{first_name}'s Quiz History*\n"]
        total_correct = sum(s.get("correct", 0) for s in user_scores)
        total_questions = sum(s.get("total", 0) for s in user_scores)
        avg = sum(s.get("score", 0) for s in user_scores) / len(user_scores)

        lines.append(f"🎯 Quizzes taken: {len(user_scores)}")
        lines.append(f"✅ Total correct: {total_correct}/{total_questions}")
        lines.append(f"📈 Average score: {avg:.1f}pts\n")

        lines.append("*Recent attempts:*")
        for s in user_scores[-5:]:
            quiz_id = s.get("quiz_id", "?")
            score = s.get("score", 0)
            correct = s.get("correct", 0)
            total = s.get("total", 0)
            lines.append(f"• Quiz {quiz_id}: {score:.0f}pts ({correct}/{total})")

        return "\n".join(lines)

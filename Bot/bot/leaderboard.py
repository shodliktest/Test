"""Leaderboard Service — RAM store dan o'qiydi."""
import logging
from typing import Dict, List
from database.ram_store import ram

logger = logging.getLogger(__name__)


class LeaderboardService:
    def __init__(self, _db=None):
        pass  # RAM dan o'qiydi, db kerak emas

    def get_global_leaderboard(self, limit=10) -> List[Dict]:
        all_scores = ram.get_all_scores()
        user_totals: Dict[int, Dict] = {}
        for s in all_scores:
            uid = s.get("user_id")
            if uid not in user_totals:
                user_totals[uid] = {
                    "user_id":        uid,
                    "username":       s.get("username"),
                    "first_name":     s.get("first_name", "?"),
                    "total_quizzes":  0,
                    "total_correct":  0,
                    "total_questions":0,
                    "avg_score":      0,
                }
            user_totals[uid]["total_quizzes"]   += 1
            user_totals[uid]["total_correct"]   += s.get("correct", 0)
            user_totals[uid]["total_questions"] += s.get("total", 0)

        for d in user_totals.values():
            tq = d["total_questions"]
            tc = d["total_correct"]
            d["avg_score"] = round(tc / tq * 100, 1) if tq else 0

        return sorted(user_totals.values(),
                      key=lambda x: x["avg_score"], reverse=True)[:limit]

    def get_user_scores(self, user_id: int) -> List[Dict]:
        return ram.get_user_history(user_id)

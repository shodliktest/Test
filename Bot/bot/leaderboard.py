"""Leaderboard — results.json dan hisoblaydi."""
import logging
from typing import Dict, List
from database import file_store as fs

logger = logging.getLogger(__name__)


class LeaderboardService:
    def __init__(self, _db=None):
        pass

    def get_global_leaderboard(self, limit=10) -> List[Dict]:
        all_results = fs.load_results()
        user_totals: Dict[int, Dict] = {}

        for r in all_results.values():
            for score in r.get("user_scores", []):
                uid = score.get("user_id")
                if not uid:
                    continue
                if uid not in user_totals:
                    user_totals[uid] = {
                        "user_id":         uid,
                        "username":        score.get("username"),
                        "first_name":      score.get("first_name", "?"),
                        "total_quizzes":   0,
                        "total_correct":   0,
                        "total_questions": 0,
                        "avg_score":       0,
                    }
                user_totals[uid]["total_quizzes"]   += 1
                user_totals[uid]["total_correct"]   += score.get("correct", 0)
                user_totals[uid]["total_questions"] += score.get("total", 0)

        for d in user_totals.values():
            tq = d["total_questions"]
            tc = d["total_correct"]
            d["avg_score"] = round(tc / tq * 100, 1) if tq else 0

        return sorted(user_totals.values(),
                      key=lambda x: x["avg_score"], reverse=True)[:limit]

    def get_user_scores(self, user_id: int) -> List[Dict]:
        all_results = fs.load_results()
        history = []
        for r in all_results.values():
            for s in r.get("user_scores", []):
                if s.get("user_id") == user_id:
                    history.append({**s, "quiz_title": r.get("quiz_title", "")})
        return history

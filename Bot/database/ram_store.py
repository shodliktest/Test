"""
RAM Store — Barcha ma'lumotlar xotirada (500 MB yetarli).
Test tugagach kanalga JSON yuboriladi.
"""
import json, logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


class RAMStore:
    def __init__(self):
        # quiz_id -> {id, title, description, time_per_question,
        #              created_by, created_at, active, questions:[]}
        self.quizzes:  Dict[str, Dict] = {}
        # session_id -> {id, quiz_id, quiz_title, group_id, ...}
        self.sessions: Dict[str, Dict] = {}
        # session_id -> [user_score_dict, ...]
        self.scores:   Dict[str, List] = {}
        # session_id -> result_dict
        self.results:  Dict[str, Dict] = {}
        # list of log dicts (max 1000)
        self.logs:     List[Dict]      = []

    # ── QUIZ ─────────────────────────────────────────
    def save_quiz(self, quiz_id, title, description,
                  created_by, time_per_question, questions) -> Dict:
        rec = {
            "type": "QUIZ", "id": quiz_id,
            "title": title, "description": description,
            "created_by": created_by,
            "time_per_question": time_per_question,
            "question_count": len(questions),
            "questions": questions,
            "active": True, "created_at": _now(),
        }
        self.quizzes[quiz_id] = rec
        return rec

    def get_quiz(self, quiz_id: str) -> Optional[Dict]:
        return self.quizzes.get(quiz_id)

    def get_all_quizzes(self) -> List[Dict]:
        return [q for q in self.quizzes.values() if q.get("active", True)]

    def delete_quiz(self, quiz_id: str) -> bool:
        q = self.quizzes.get(quiz_id)
        if q:
            q["active"] = False; q["deleted_at"] = _now(); return True
        return False

    # ── SESSION ──────────────────────────────────────
    def save_session(self, session_id, quiz_id, quiz_title,
                     group_id, group_title, started_by) -> Dict:
        rec = {
            "type": "SESSION", "id": session_id,
            "quiz_id": quiz_id, "quiz_title": quiz_title,
            "group_id": group_id, "group_title": group_title,
            "started_by": started_by, "started_at": _now(), "status": "active",
        }
        self.sessions[session_id] = rec
        self.scores[session_id]   = []
        return rec

    def end_session(self, session_id: str):
        s = self.sessions.get(session_id)
        if s:
            s["status"] = "completed"; s["ended_at"] = _now()

    def get_sessions(self) -> List[Dict]:
        return list(self.sessions.values())

    # ── SCORES / RESULTS ─────────────────────────────
    def save_scores(self, session_id: str, scores: List[Dict]):
        self.scores[session_id] = scores

    def save_result(self, session_id, quiz_id, group_id,
                    participants, avg_score, top_scorer) -> Dict:
        rec = {
            "type": "RESULT", "session_id": session_id,
            "quiz_id": quiz_id, "group_id": group_id,
            "participants": participants, "avg_score": avg_score,
            "top_scorer": top_scorer, "completed_at": _now(),
        }
        self.results[session_id] = rec
        return rec

    def get_scores_for_session(self, session_id: str) -> List[Dict]:
        return self.scores.get(session_id, [])

    def get_all_scores(self) -> List[Dict]:
        out = []
        for lst in self.scores.values():
            out.extend(lst)
        return out

    def get_user_history(self, user_id: int) -> List[Dict]:
        return [s for s in self.get_all_scores() if s.get("user_id") == user_id]

    # ── LOG ──────────────────────────────────────────
    def add_log(self, level: str, msg: str, ctx: dict = None):
        self.logs.append({"type":"LOG","level":level,"message":msg,
                          "context":ctx or {},"timestamp":_now()})
        if len(self.logs) > 1000:
            self.logs = self.logs[-800:]

    def get_logs(self, limit=100) -> List[Dict]:
        return self.logs[-limit:]

    # ── TELEGRAM EKSPORT ─────────────────────────────
    def quiz_to_telegram_text(self, quiz_id: str) -> Optional[str]:
        q = self.quizzes.get(quiz_id)
        return ("QUIZ:" + json.dumps(q, ensure_ascii=False)) if q else None

    def result_to_telegram_text(self, session_id: str) -> Optional[str]:
        result  = self.results.get(session_id)
        if not result:
            return None
        payload = {
            **result,
            "session":     self.sessions.get(session_id),
            "user_scores": self.scores.get(session_id, []),
        }
        return "RESULT:" + json.dumps(payload, ensure_ascii=False)

    # ── TELEGRAM IMPORT ──────────────────────────────
    def load_from_text(self, text: str) -> bool:
        """Kanal xabaridan JSON ni parse qilib RAM ga yuklaydi."""
        try:
            if text.startswith("QUIZ:"):
                d = json.loads(text[5:])
                if d.get("id"):
                    self.quizzes[d["id"]] = d
                    return True
            elif text.startswith("RESULT:"):
                d   = json.loads(text[7:])
                sid = d.get("session_id")
                if sid:
                    self.scores[sid]   = d.pop("user_scores", [])
                    sess               = d.pop("session", None)
                    self.results[sid]  = d
                    if sess:
                        self.sessions[sid] = sess
                    return True
        except Exception as e:
            logger.warning(f"load_from_text xato: {e}")
        return False

    def stats(self) -> Dict:
        return {
            "quizzes":  len(self.quizzes),
            "sessions": len(self.sessions),
            "results":  len(self.results),
            "logs":     len(self.logs),
            "scores":   sum(len(v) for v in self.scores.values()),
        }


# Global singleton
ram = RAMStore()

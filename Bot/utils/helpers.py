"""
Helper utilities for the Telegram Quiz Platform
"""
import json
import hashlib
import random
import string
from datetime import datetime
from typing import Any, Dict, List, Optional


def generate_id(prefix: str = "id") -> str:
    """Generate a unique ID with prefix."""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}_{timestamp}_{random_suffix}"


def format_json_message(data: Dict[str, Any]) -> str:
    """Format data as a JSON message for Telegram DB group."""
    return f"📦 DB_RECORD\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```"


def parse_json_from_message(text: str) -> Optional[Dict[str, Any]]:
    """Extract and parse JSON from a Telegram message."""
    if not text or "DB_RECORD" not in text:
        return None
    try:
        # Extract JSON between code block markers
        start = text.find("```json\n") + 8
        end = text.rfind("\n```")
        if start < 8 or end == -1:
            return None
        json_str = text[start:end].strip()
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        return None


def format_duration(seconds: int) -> str:
    """Format seconds into human readable duration."""
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    secs = seconds % 60
    if secs == 0:
        return f"{minutes}m"
    return f"{minutes}m {secs}s"


def format_score(correct: int, total: int) -> str:
    """Format score display."""
    percentage = (correct / total * 100) if total > 0 else 0
    return f"{correct}/{total} ({percentage:.1f}%)"


def get_rank_emoji(rank: int) -> str:
    """Get emoji for leaderboard rank."""
    emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
    return emojis.get(rank, f"{rank}.")


def sanitize_text(text: str) -> str:
    """Sanitize text for Telegram markdown."""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text to max length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def calculate_score(correct_answers: int, total_questions: int, 
                     time_bonus: float = 0.0) -> float:
    """Calculate quiz score with optional time bonus."""
    base_score = (correct_answers / total_questions * 100) if total_questions > 0 else 0
    return round(base_score + time_bonus, 2)


def format_leaderboard(scores: List[Dict]) -> str:
    """Format leaderboard for display."""
    if not scores:
        return "📊 No scores yet!"
    
    lines = ["🏆 *LEADERBOARD*\n"]
    for i, entry in enumerate(scores[:10], 1):
        rank_emoji = get_rank_emoji(i)
        name = entry.get("username") or entry.get("first_name", "Unknown")
        score = entry.get("score", 0)
        correct = entry.get("correct", 0)
        total = entry.get("total", 0)
        lines.append(f"{rank_emoji} {name}: {score:.1f}pts ({correct}/{total})")
    
    return "\n".join(lines)


def now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.utcnow().isoformat() + "Z"


def build_quiz_record(quiz_id: str, title: str, description: str,
                       created_by: str, question_count: int,
                       time_per_question: int = 30) -> Dict:
    """Build a QUIZ database record."""
    return {
        "type": "QUIZ",
        "id": quiz_id,
        "title": title,
        "description": description,
        "created_by": created_by,
        "questions": question_count,
        "time_per_question": time_per_question,
        "created_at": now_iso(),
        "active": True
    }


def build_question_record(quiz_id: str, question_index: int,
                           question_text: str, options: List[str],
                           correct_index: int, question_type: str = "multiple_choice",
                           explanation: str = "", image_url: str = "") -> Dict:
    """Build a QUESTION database record."""
    return {
        "type": "QUESTION",
        "quiz_id": quiz_id,
        "index": question_index,
        "text": question_text,
        "options": options,
        "correct_index": correct_index,
        "question_type": question_type,
        "explanation": explanation,
        "image_url": image_url,
        "created_at": now_iso()
    }


def build_result_record(session_id: str, quiz_id: str, group_id: int,
                         participants: int, avg_score: float,
                         top_scorer: str) -> Dict:
    """Build a RESULT database record."""
    return {
        "type": "RESULT",
        "session_id": session_id,
        "quiz_id": quiz_id,
        "group_id": group_id,
        "participants": participants,
        "avg_score": avg_score,
        "top_scorer": top_scorer,
        "completed_at": now_iso()
    }


def build_user_score_record(session_id: str, quiz_id: str,
                              user_id: int, username: str,
                              first_name: str, correct: int,
                              total: int, score: float) -> Dict:
    """Build a USER_SCORE database record."""
    return {
        "type": "USER_SCORE",
        "session_id": session_id,
        "quiz_id": quiz_id,
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "correct": correct,
        "total": total,
        "score": score,
        "recorded_at": now_iso()
    }


def build_log_record(level: str, message: str, context: Dict = None) -> Dict:
    """Build a LOG database record."""
    return {
        "type": "LOG",
        "level": level,  # INFO, WARNING, ERROR
        "message": message,
        "context": context or {},
        "timestamp": now_iso()
    }


def build_session_record(session_id: str, quiz_id: str, quiz_title: str,
                          group_id: int, group_title: str,
                          started_by: int) -> Dict:
    """Build a SESSION database record."""
    return {
        "type": "SESSION",
        "id": session_id,
        "quiz_id": quiz_id,
        "quiz_title": quiz_title,
        "group_id": group_id,
        "group_title": group_title,
        "started_by": started_by,
        "started_at": now_iso(),
        "status": "active"
    }

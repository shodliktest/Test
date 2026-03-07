"""
Configuration management for Telegram Quiz Platform
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    # Telegram Bot Configuration
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    
    # Private Telegram group used as database
    DB_GROUP_ID: str = os.getenv("DB_GROUP_ID", "-1001234567890")
    
    # Admin Telegram user IDs (comma-separated in env)
    ADMIN_IDS: list = field(default_factory=lambda: [
        int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",") if x.strip()
    ])
    
    # Firebase (optional - minimal usage)
    FIREBASE_CREDENTIALS_PATH: Optional[str] = os.getenv("FIREBASE_CREDENTIALS_PATH", None)
    FIREBASE_PROJECT_ID: Optional[str] = os.getenv("FIREBASE_PROJECT_ID", None)
    
    # Quiz Settings
    DEFAULT_QUESTION_TIMEOUT: int = int(os.getenv("DEFAULT_QUESTION_TIMEOUT", "30"))  # seconds
    MAX_QUESTIONS_PER_QUIZ: int = int(os.getenv("MAX_QUESTIONS_PER_QUIZ", "50"))
    MAX_OPTIONS_PER_QUESTION: int = 4
    
    # Anti-cheat
    ANSWER_LOCK_BUFFER: int = 2  # seconds after timer to accept late answers
    
    # Leaderboard
    LEADERBOARD_TOP_N: int = 10
    
    # Streamlit Admin Panel
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")
    
    # Message prefixes for DB parsing
    MSG_TYPE_QUIZ = "QUIZ"
    MSG_TYPE_QUESTION = "QUESTION"
    MSG_TYPE_RESULT = "RESULT"
    MSG_TYPE_USER_SCORE = "USER_SCORE"
    MSG_TYPE_LOG = "LOG"
    MSG_TYPE_SESSION = "SESSION"


config = Config()

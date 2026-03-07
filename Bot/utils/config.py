"""
Configuration management for Telegram Quiz Platform

Qiymatlarni o'qish tartibi (ustunlikdan pastga):
  1. Streamlit Cloud → st.secrets  (secrets.toml)
  2. Local           → os.environ  (.env fayl yoki terminal)
  3. Default         → hardcoded fallback
"""
import os
from typing import Optional


def _secret(key: str, default: str = "") -> str:
    """
    Avval Streamlit secrets dan o'qiydi,
    topilmasa environment variable dan oladi,
    u ham yo'q bo'lsa default qaytaradi.
    """
    # 1) Streamlit secrets
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val is not None:
            return str(val)
    except Exception:
        pass

    # 2) Environment variable
    val = os.getenv(key)
    if val is not None:
        return val

    # 3) Default
    return default


class Config:
    # ── Telegram Bot ──────────────────────────────────
    @property
    def BOT_TOKEN(self) -> str:
        return _secret("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

    @property
    def DB_GROUP_ID(self) -> str:
        return _secret("DB_GROUP_ID", "-1001234567890")

    @property
    def ADMIN_IDS(self) -> list:
        raw = _secret("ADMIN_IDS", "123456789")
        return [int(x.strip()) for x in raw.split(",") if x.strip().lstrip("-").isdigit()]

    # ── Firebase (ixtiyoriy) ───────────────────────────
    @property
    def FIREBASE_CREDENTIALS_PATH(self) -> Optional[str]:
        v = _secret("FIREBASE_CREDENTIALS_PATH", "")
        return v if v else None

    @property
    def FIREBASE_PROJECT_ID(self) -> Optional[str]:
        v = _secret("FIREBASE_PROJECT_ID", "")
        return v if v else None

    # ── Quiz sozlamalari ───────────────────────────────
    @property
    def DEFAULT_QUESTION_TIMEOUT(self) -> int:
        return int(_secret("DEFAULT_QUESTION_TIMEOUT", "30"))

    @property
    def MAX_QUESTIONS_PER_QUIZ(self) -> int:
        return int(_secret("MAX_QUESTIONS_PER_QUIZ", "50"))

    MAX_OPTIONS_PER_QUESTION: int = 4
    ANSWER_LOCK_BUFFER: int = 2
    LEADERBOARD_TOP_N: int = 10

    # ── Streamlit Admin Panel ──────────────────────────
    @property
    def ADMIN_USERNAME(self) -> str:
        return _secret("ADMIN_USERNAME", "admin")

    @property
    def ADMIN_PASSWORD(self) -> str:
        return _secret("ADMIN_PASSWORD", "admin123")

    # ── DB xabar turlari ──────────────────────────────
    MSG_TYPE_QUIZ       = "QUIZ"
    MSG_TYPE_QUESTION   = "QUESTION"
    MSG_TYPE_RESULT     = "RESULT"
    MSG_TYPE_USER_SCORE = "USER_SCORE"
    MSG_TYPE_LOG        = "LOG"
    MSG_TYPE_SESSION    = "SESSION"


config = Config()

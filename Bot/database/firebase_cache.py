"""
Firebase Cache Layer (Optional)
Used minimally to avoid daily quota limits.
Only caches quiz metadata and active sessions.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Flag to track Firebase availability
FIREBASE_AVAILABLE = False
_db = None


def _init_firebase():
    """Lazily initialize Firebase."""
    global FIREBASE_AVAILABLE, _db
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        from utils.config import config

        if not config.FIREBASE_CREDENTIALS_PATH:
            logger.info("Firebase credentials not configured, skipping Firebase init")
            return False

        if not firebase_admin._apps:
            cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred, {
                'projectId': config.FIREBASE_PROJECT_ID
            })

        _db = firestore.client()
        FIREBASE_AVAILABLE = True
        logger.info("Firebase initialized successfully")
        return True
    except ImportError:
        logger.info("firebase-admin not installed, Firebase caching disabled")
        return False
    except Exception as e:
        logger.warning(f"Firebase init failed: {e}, continuing without Firebase")
        return False


class FirebaseCache:
    """
    Optional Firebase Firestore cache.
    Falls back gracefully if Firebase is unavailable.
    Minimal usage to avoid quota exhaustion.
    """

    def __init__(self):
        self._available = _init_firebase()

    @property
    def available(self) -> bool:
        return self._available and _db is not None

    async def cache_quiz_list(self, quizzes: List[Dict]) -> bool:
        """Cache the quiz list for faster admin panel access."""
        if not self.available:
            return False
        try:
            doc_ref = _db.collection("cache").document("quiz_list")
            doc_ref.set({
                "quizzes": quizzes,
                "updated_at": __import__("utils.helpers", fromlist=["now_iso"]).now_iso()
            })
            return True
        except Exception as e:
            logger.warning(f"Firebase cache write failed: {e}")
            return False

    async def get_cached_quiz_list(self) -> Optional[List[Dict]]:
        """Get cached quiz list."""
        if not self.available:
            return None
        try:
            doc = _db.collection("cache").document("quiz_list").get()
            if doc.exists:
                return doc.to_dict().get("quizzes", [])
        except Exception as e:
            logger.warning(f"Firebase cache read failed: {e}")
        return None

    async def cache_active_session(self, session_id: str, data: Dict) -> bool:
        """Cache an active quiz session."""
        if not self.available:
            return False
        try:
            _db.collection("active_sessions").document(session_id).set(data)
            return True
        except Exception as e:
            logger.warning(f"Firebase session cache failed: {e}")
            return False

    async def remove_active_session(self, session_id: str) -> bool:
        """Remove an active session from cache."""
        if not self.available:
            return False
        try:
            _db.collection("active_sessions").document(session_id).delete()
            return True
        except Exception as e:
            logger.warning(f"Firebase session remove failed: {e}")
            return False

    async def get_active_sessions(self) -> List[Dict]:
        """Get all active sessions."""
        if not self.available:
            return []
        try:
            docs = _db.collection("active_sessions").stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.warning(f"Firebase active sessions read failed: {e}")
            return []

    async def cache_user_score(self, user_id: int, quiz_id: str, score: float) -> bool:
        """Cache a user's best score for quick leaderboard access."""
        if not self.available:
            return False
        try:
            doc_id = f"{user_id}_{quiz_id}"
            existing = _db.collection("scores").document(doc_id).get()
            if existing.exists:
                current = existing.to_dict().get("score", 0)
                if score <= current:
                    return True  # Don't overwrite better score
            _db.collection("scores").document(doc_id).set({
                "user_id": user_id,
                "quiz_id": quiz_id,
                "score": score,
                "updated_at": __import__("utils.helpers", fromlist=["now_iso"]).now_iso()
            })
            return True
        except Exception as e:
            logger.warning(f"Firebase score cache failed: {e}")
            return False

"""
File Store — Arxitektura:

  data/quizzes/
    quizzes.json          ← faqat ID index: {"ids": ["quiz_abc", "quiz_xyz"]}
    quiz_abc.json         ← to'liq test (meta + questions)
    quiz_xyz.json         ← to'liq test

  data/
    results.json          ← yakuniy natijalar (doimiy)

RAM:
  - Faqat faol sessiya testlari yuklanadi (lazy)
  - Sessiya tugagach test RAM dan o'chiriladi
  - Natijalar sessiya davomida RAM da, e'lon qilinib tozalanadi
"""
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _get_data_dir() -> Path:
    if os.path.exists("/mount/src"):
        d = Path("/tmp/quiz_data")
    else:
        d = Path("./data")
    d.mkdir(parents=True, exist_ok=True)
    (d / "quizzes").mkdir(exist_ok=True)
    return d


DATA_DIR    = _get_data_dir()
QUIZ_DIR    = DATA_DIR / "quizzes"
INDEX_FILE  = QUIZ_DIR / "quizzes.json"
RESULTS_FILE = DATA_DIR / "results.json"


def _write(path: Path, data) -> bool:
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return True
    except Exception as e:
        logger.error(f"❌ Yozish xatosi {path.name}: {e}")
        return False


def _read(path: Path, default=None):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"❌ O'qish xatosi {path.name}: {e}")
    return default


# ════════════════════════════════════════════════════
# QUIZ — SAQLASH
# ════════════════════════════════════════════════════

def save_quiz(quiz_id: str, quiz_data: dict) -> bool:
    """Testni quiz_{id}.json ga yozadi va indexga qo'shadi."""
    # 1. Alohida fayl
    quiz_file = QUIZ_DIR / f"{quiz_id}.json"
    if not _write(quiz_file, quiz_data):
        return False

    # 2. Index ga qo'shish
    index = _read(INDEX_FILE, {"ids": []})
    if quiz_id not in index["ids"]:
        index["ids"].append(quiz_id)
        _write(INDEX_FILE, index)

    logger.info(f"💾 Saqlandi: {quiz_file.name}")
    return True


def delete_quiz_file(quiz_id: str) -> bool:
    """Test faylini o'chiradi va indexdan chiqaradi."""
    quiz_file = QUIZ_DIR / f"{quiz_id}.json"
    try:
        if quiz_file.exists():
            quiz_file.unlink()
    except Exception as e:
        logger.error(f"❌ O'chirish xatosi: {e}")

    index = _read(INDEX_FILE, {"ids": []})
    if quiz_id in index["ids"]:
        index["ids"].remove(quiz_id)
        _write(INDEX_FILE, index)
    return True


def load_quiz(quiz_id: str) -> Optional[dict]:
    """Bitta test faylini o'qiydi."""
    path = QUIZ_DIR / f"{quiz_id}.json"
    data = _read(path)
    if data:
        logger.info(f"📂 Yuklandi: {path.name}")
    return data


def get_all_quiz_ids() -> List[str]:
    """Index dan barcha test ID larini qaytaradi."""
    index = _read(INDEX_FILE, {"ids": []})
    return index.get("ids", [])


def load_quiz_meta(quiz_id: str) -> Optional[dict]:
    """Faqat meta (questions yo'q) qaytaradi — tez."""
    data = load_quiz(quiz_id)
    if not data:
        return None
    return {k: v for k, v in data.items() if k != "questions"}


def get_all_quizzes_meta() -> List[dict]:
    """Barcha testlarning meta ma'lumotlarini qaytaradi."""
    metas = []
    for qid in get_all_quiz_ids():
        m = load_quiz_meta(qid)
        if m and m.get("active", True):
            metas.append(m)
    return metas


# ════════════════════════════════════════════════════
# RESULTS — SAQLASH
# ════════════════════════════════════════════════════

def save_result(session_id: str, result_data: dict) -> bool:
    """Natijani results.json ga qo'shib yozadi."""
    all_results = _read(RESULTS_FILE, {})
    all_results[session_id] = result_data
    ok = _write(RESULTS_FILE, all_results)
    if ok:
        logger.info(f"💾 Natija saqlandi: {session_id}")
    return ok


def load_results() -> dict:
    """Barcha natijalarni qaytaradi."""
    return _read(RESULTS_FILE, {})


# ════════════════════════════════════════════════════
# FAYL MA'LUMOTLARI
# ════════════════════════════════════════════════════

def file_info() -> dict:
    ids = get_all_quiz_ids()
    total_size = sum(
        (QUIZ_DIR / f"{qid}.json").stat().st_size
        for qid in ids
        if (QUIZ_DIR / f"{qid}.json").exists()
    )
    res_size = RESULTS_FILE.stat().st_size if RESULTS_FILE.exists() else 0
    return {
        "data_dir":    str(DATA_DIR),
        "quiz_count":  len(ids),
        "quiz_ids":    ids,
        "quizzes_kb":  round(total_size / 1024, 1),
        "results_kb":  round(res_size / 1024, 1),
    }

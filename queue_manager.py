import logging
import threading
from datetime import datetime, timezone
from uuid import uuid4

import database as db
from config import TEMP_DIR

_lock = threading.Lock()
_pending: dict[int, list[dict]] = {}  # user_id -> [items]
_processing: dict[int, dict | None] = {}
logger = logging.getLogger(__name__)


def add_to_queue(user_id: int, url: str, settings: dict) -> dict:
    user = db.get_user(user_id)
    if not user:
        raise Exception("not_registered")
    max_q = user.get("max_queue", 3)
    daily_limit = user.get("daily_limit", 10)
    date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_used = user.get("daily_counts", {}).get(date_key, 0)

    item = {
        "id": uuid4().hex[:8],
        "user_id": user_id,
        "url": url,
        "status": "waiting",
        "settings": dict(settings),
        "added_at": datetime.now(timezone.utc).isoformat(),
    }

    with _lock:
        queue = _pending.get(user_id, [])
        if len(queue) >= max_q:
            raise Exception("max_queue")
        if today_used >= daily_limit:
            raise Exception("max_daily")
        queue.append(item)
        _pending[user_id] = queue

    logger.info("Queue add user=%d url=%s id=%s", user_id, url, item["id"])
    return item


def get_user_queue(user_id: int) -> list:
    with _lock:
        return list(_pending.get(user_id, []))


def get_current(user_id: int) -> dict | None:
    with _lock:
        return _processing.get(user_id)


def get_position(user_id: int, item_id: str) -> int:
    with _lock:
        for i, item in enumerate(_pending.get(user_id, [])):
            if item["id"] == item_id:
                return i + 1
    return -1


def cancel_item(user_id: int, item_id: str) -> bool:
    with _lock:
        queue = _pending.get(user_id, [])
        for i, item in enumerate(queue):
            if item["id"] == item_id and item["status"] == "waiting":
                queue.pop(i)
                _pending[user_id] = queue
                logger.info("Queue cancelled user=%d id=%s", user_id, item_id)
                return True
    return False


def start_processing(user_id: int, item_id: str) -> None:
    with _lock:
        queue = _pending.get(user_id, [])
        for i, item in enumerate(queue):
            if item["id"] == item_id and item["status"] == "waiting":
                item["status"] = "processing"
                _processing[user_id] = item
                queue.pop(i)
                _pending[user_id] = queue
                logger.info("Queue start user=%d id=%s", user_id, item_id)
                return
    logger.warning("start_processing: item %s not found for user %d", item_id, user_id)


def finish_processing(user_id: int, item_id: str) -> None:
    with _lock:
        _processing[user_id] = None


def get_all_waiting() -> list:
    with _lock:
        result = []
        for uid, items in _pending.items():
            result.extend(items)
        return result

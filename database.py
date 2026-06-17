import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone

from config import PLANS

DB_PATH = "data/users_db.json"
_lock = threading.Lock()
logger = logging.getLogger(__name__)


def _read() -> dict:
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write(data: dict) -> None:
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_user(user_id: int, plan: str, days: int, api_key: str,
             project_id: str, social_account_id: str, username: str = "") -> dict:
    now = datetime.now(timezone.utc)
    plan_cfg = PLANS.get(plan, PLANS["trial"])
    user = {
        "user_id": user_id,
        "username": username,
        "plan": plan,
        "status": "active",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(days=days)).isoformat(),
        "woopsocial_api_key": api_key,
        "woopsocial_project_id": project_id,
        "woopsocial_social_account_id": social_account_id,
        "daily_limit": plan_cfg["daily_limit"],
        "max_queue": plan_cfg["max_queue"],
        "language": "ar",
        "settings": {
            "speed": 1.1,
            "split": 10,
            "schedule": 15,
        },
        "stats": {
            "total_videos": 0,
            "total_parts": 0,
            "last_active": now.isoformat(),
        },
        "daily_counts": {},
        "last_slot": None,
    }
    with _lock:
        db = _read()
        db[str(user_id)] = user
        _write(db)
    logger.info("User %d added (plan=%s, days=%d)", user_id, plan, days)
    return user


def get_user(user_id: int) -> dict | None:
    with _lock:
        db = _read()
        return db.get(str(user_id))


def update_user(user_id: int, updates: dict) -> bool:
    with _lock:
        db = _read()
        key = str(user_id)
        if key not in db:
            return False
        user = db[key]
        for k, v in updates.items():
            if isinstance(v, dict) and isinstance(user.get(k), dict):
                user[k].update(v)
            else:
                user[k] = v
        _write(db)
    logger.debug("User %d updated: %s", user_id, set(updates.keys()))
    return True


def delete_user(user_id: int) -> bool:
    with _lock:
        db = _read()
        key = str(user_id)
        if key not in db:
            return False
        del db[key]
        _write(db)
    logger.info("User %d deleted", user_id)
    return True


def get_all_users() -> list:
    with _lock:
        db = _read()
        return list(db.values())


def is_active(user_id: int) -> tuple:
    user = get_user(user_id)
    if not user:
        return False, "not_registered"
    if user["status"] == "suspended":
        return False, "suspended"
    if user["status"] == "expired":
        return False, "expired"
    expires = datetime.fromisoformat(user["expires_at"])
    if expires < datetime.now(timezone.utc):
        set_user_status(user_id, "expired")
        return False, "expired"
    return True, ""


def add_days(user_id: int, days: int) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    current = datetime.fromisoformat(user["expires_at"])
    new_expiry = current + timedelta(days=days)
    return update_user(user_id, {"expires_at": new_expiry.isoformat()})


def change_plan(user_id: int, plan: str) -> bool:
    cfg = PLANS.get(plan)
    if not cfg:
        return False
    return update_user(user_id, {
        "plan": plan,
        "daily_limit": cfg["daily_limit"],
        "max_queue": cfg["max_queue"],
    })


def set_user_status(user_id: int, status: str) -> bool:
    return update_user(user_id, {"status": status})


def update_stats(user_id: int, parts_count: int) -> None:
    user = get_user(user_id)
    if not user:
        return
    now = datetime.now(timezone.utc)
    date_key = now.strftime("%Y-%m-%d")
    daily = user.get("daily_counts", {})
    daily[date_key] = daily.get(date_key, 0) + 1
    update_user(user_id, {
        "stats": {
            "total_videos": user["stats"]["total_videos"] + 1,
            "total_parts": user["stats"]["total_parts"] + parts_count,
            "last_active": now.isoformat(),
        },
        "daily_counts": daily,
    })


def get_stats_summary() -> dict:
    users = get_all_users()
    total = len(users)
    active = sum(1 for u in users if u["status"] == "active")
    suspended = sum(1 for u in users if u["status"] == "suspended")
    expired = sum(1 for u in users if u["status"] == "expired")
    trial = sum(1 for u in users if u.get("plan") == "trial")
    return {"total": total, "active": active, "suspended": suspended,
            "expired": expired, "trial": trial}

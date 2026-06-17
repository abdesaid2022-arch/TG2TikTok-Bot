import logging
from datetime import datetime, timedelta, timezone

import requests

import database as db
from config import WOOPSOCIAL_BASE

logger = logging.getLogger(__name__)


def _scheduled_at(user_id: int, schedule_secs: int) -> str:
    user = db.get_user(user_id)
    last = user.get("last_slot")
    now = datetime.now(timezone.utc)
    if last:
        base = datetime.fromisoformat(last)
        if base < now:
            base = now
    else:
        base = now
    return (base + timedelta(seconds=schedule_secs)).isoformat()


def send_to_woopsocial(user_id: int, parts: list, title: str,
                       schedule_secs: int, api_key: str,
                       project_id: str, social_account_id: str) -> list[dict]:
    results = []
    for p in parts:
        sched = _scheduled_at(user_id, schedule_secs)
        caption = f"الجزء {p['part']} | {title}"
        body = {
            "project_id": project_id,
            "social_account_id": social_account_id,
            "content": caption,
            "media_url": p["drive_url"],
            "scheduled_at": sched,
        }
        last_exc = None
        for attempt in range(3):
            try:
                r = requests.post(
                    f"{WOOPSOCIAL_BASE}/posts",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=body,
                    timeout=30,
                )
                r.raise_for_status()
                db.update_user(user_id, {"last_slot": sched})
                results.append({"part": p["part"], "scheduled_at": sched, "status": "ok"})
                logger.info("WoopSocial scheduled part %d at %s", p["part"], sched)
                break
            except Exception as exc:
                last_exc = exc
                logger.warning("WoopSocial attempt %d/3 part %d failed: %s", attempt+1, p["part"], exc)
        else:
            results.append({"part": p["part"], "status": "error", "error": str(last_exc)})
    return results

import logging
import threading
import time

from uploader import get_drive_service

logger = logging.getLogger(__name__)

_pending: list[dict] = []
_lock = threading.Lock()
_cleaner_started = False


def schedule_deletion(file_id: str, minutes: int) -> None:
    with _lock:
        _pending.append({"file_id": file_id, "delete_at": time.time() + minutes * 60})


def _cleanup_loop() -> None:
    while True:
        now = time.time()
        to_delete = []
        with _lock:
            remaining = []
            for entry in _pending:
                if entry["delete_at"] <= now:
                    to_delete.append(entry["file_id"])
                else:
                    remaining.append(entry)
            _pending[:] = remaining
        for fid in to_delete:
            try:
                service = get_drive_service()
                service.files().delete(fileId=fid).execute()
                logger.info("Cleaned Drive file %s", fid)
            except Exception as exc:
                logger.warning("Drive cleanup failed for %s: %s", fid, exc)
        time.sleep(30)


def start_cleaner() -> None:
    global _cleaner_started
    if _cleaner_started:
        return
    _cleaner_started = True
    t = threading.Thread(target=_cleanup_loop, daemon=True)
    t.start()
    logger.info("Drive cleaner started")

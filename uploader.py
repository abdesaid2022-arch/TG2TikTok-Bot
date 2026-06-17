import logging
import os
import pickle
import threading
from datetime import datetime, timedelta, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import DRIVE_FOLDER_ID, DRIVE_DELETE_AFTER_MINUTES

logger = logging.getLogger(__name__)
_delayed_deletions: list[threading.Timer] = []

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
PICKLE_PATH = "data/token.pickle"
CREDS_PATH = "data/credentials.json"


def get_drive_service():
    creds = None
    if os.path.exists(PICKLE_PATH):
        try:
            with open(PICKLE_PATH, "rb") as f:
                creds = pickle.load(f)
        except Exception as exc:
            logger.error("pickle load failed: %s — rebuilding from env", exc)
            creds = None

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(PICKLE_PATH, "wb") as f:
            pickle.dump(creds, f)

    if not creds or not creds.valid:
        if os.path.exists(CREDS_PATH):
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        else:
            raise Exception("credentials.json not found and no valid token.pickle")
        with open(PICKLE_PATH, "wb") as f:
            pickle.dump(creds, f)

    return build("drive", "v3", credentials=creds)


def create_user_folder(service, user_id: int, title: str) -> str:
    folder_meta = {
        "name": f"{user_id} - {title[:50]}",
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [DRIVE_FOLDER_ID],
    }
    folder = service.files().create(body=folder_meta, fields="id").execute()
    logger.info("Created Drive folder %s for user %d", folder["id"], user_id)
    return folder["id"]


def upload_part(service, file_path: str, folder_id: str, name: str) -> tuple:
    media = MediaFileUpload(file_path, chunksize=5 * 1024 * 1024, resumable=True)
    file_meta = {"name": name, "parents": [folder_id]}
    last_exc = None
    for attempt in range(3):
        try:
            drive_file = service.files().create(
                body=file_meta, media_body=media, fields="id,webViewLink"
            ).execute()
            fid = drive_file["id"]
            service.permissions().create(
                fileId=fid, body={"type": "anyone", "role": "reader"}
            ).execute()
            dl_url = f"https://drive.google.com/uc?export=download&id={fid}"
            logger.info("Uploaded %s -> %s", name, dl_url)
            return fid, dl_url
        except Exception as exc:
            last_exc = exc
            logger.warning("Upload attempt %d/3 failed for %s: %s", attempt+1, name, exc)
            media = MediaFileUpload(file_path, chunksize=5*1024*1024, resumable=True)
    raise Exception(f"فشل رفع {name} بعد 3 محاولات: {last_exc}")


def upload_all_parts(user_id: int, parts: list, title: str) -> list[dict]:
    service = get_drive_service()
    folder_id = create_user_folder(service, user_id, title)
    results = []
    for p in parts:
        name = f"{title[:40]}_part{p['index']:03d}.mp4"
        fid, url = upload_part(service, p["path"], folder_id, name)
        results.append({"part": p["index"], "drive_url": url, "file_id": fid})
        schedule_deletion(fid, DRIVE_DELETE_AFTER_MINUTES)
    return results


def schedule_deletion(file_id: str, minutes: int) -> None:
    def _del():
        try:
            service = get_drive_service()
            service.files().delete(fileId=file_id).execute()
            logger.info("Deleted Drive file %s after %dmin", file_id, minutes)
        except Exception as exc:
            logger.warning("Failed to delete %s: %s", file_id, exc)
    t = threading.Timer(minutes * 60, _del)
    t.daemon = True
    t.start()
    _delayed_deletions.append(t)

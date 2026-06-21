import logging
import os
import re
import subprocess
import sys
from pathlib import Path

from config import TEMP_DIR, TIMEOUT

logger = logging.getLogger(__name__)

YT_RE = re.compile(
    r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/(watch\?v=|embed/|v/|shorts/)?([\w-]{11})"
)
COOKIES_PATH = "data/cookies.txt"


async def update_ytdlp() -> None:
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                       capture_output=True, timeout=60)
        logger.info("yt-dlp updated")
    except Exception as exc:
        logger.warning("yt-dlp update failed: %s", exc)


def is_valid_youtube_url(url: str) -> bool:
    return bool(YT_RE.match(url.strip()))


def extract_video_id(url: str) -> str | None:
    m = YT_RE.match(url.strip())
    return m.group(5) if m else None


def get_video_info(url: str) -> dict:
    import yt_dlp
    opts = _base_opts()
    opts["playlist_items"] = "1"
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration", 0),
            "uploader": info.get("uploader", ""),
        }


def download_video(url: str, file_key: str) -> str | None:
    import yt_dlp
    os.makedirs(TEMP_DIR, exist_ok=True)
    outtmpl = os.path.join(TEMP_DIR, f"{file_key}.%(ext)s")
    fmt_fallbacks = [
        "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "bestvideo+bestaudio/best",
        "best[ext=mp4]/best",
    ]
    clients = ["ios", "android", "mweb"]

    for client in clients:
        opts = _base_opts()
        opts["outtmpl"] = outtmpl
        opts["format"] = fmt_fallbacks[0]
        opts.setdefault("extractor_args", {})
        opts["extractor_args"].setdefault("youtube", {})["player_client"] = [client]
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                fp = ydl.prepare_filename(info)
                for ext in ["mp4", "webm", "mkv"]:
                    p = Path(str(fp).rsplit(".", 1)[0] + f".{ext}")
                    if p.exists() and p.stat().st_size > 10240:
                        logger.info("Downloaded %s with client=%s", p.name, client)
                        return str(p)
                p = Path(fp)
                if p.exists() and p.stat().st_size > 10240:
                    return str(p)
        except Exception as exc:
            err = str(exc).lower()
            if "sign in" in err or "cookie" in err or "bot" in err or "403" in err:
                logger.warning("Client %s blocked (%s), trying next", client, exc)
                continue
            if "private" in err or "unavailable" in err:
                raise Exception(f"❌ الفيديو خاص أو غير متاح: {exc}")
            raise Exception(f"❌ فشل التحميل: {exc}")

    raise Exception("cookies_expired")


def _base_opts() -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "ignoreerrors": False,
        "noprogress": True,
    }
    if os.path.exists(COOKIES_PATH):
        opts["cookiefile"] = COOKIES_PATH
    po = os.environ.get("YT_PO_TOKEN")
    vd = os.environ.get("YT_VISITOR_DATA")
    if po and vd:
        opts["extractor_args"] = {"youtube": {"po_token": [po], "visitor_data": [vd]}}
    return opts

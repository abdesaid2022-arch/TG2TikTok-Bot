import logging
import os
import subprocess

from config import TEMP_DIR

logger = logging.getLogger(__name__)

OVERLAP = 5
MIN_LAST_SEGMENT = 30


def _has_audio(path: str) -> bool:
    r = subprocess.run([
        "ffprobe", "-i", path,
        "-show_streams", "-select_streams", "a",
        "-loglevel", "error"
    ], capture_output=True, text=True)
    return bool(r.stdout.strip())


def _validate(path: str) -> None:
    if not os.path.exists(path):
        raise Exception("الملف غير موجود")
    if os.path.getsize(path) < 10240:
        raise Exception("الملف تالف أو صغير جداً")
    r = subprocess.run([
        "ffprobe", "-i", path,
        "-show_streams", "-select_streams", "v",
        "-loglevel", "error"
    ], capture_output=True, text=True)
    if not r.stdout.strip():
        raise Exception("الملف لا يحتوي فيديو — حاول مجدداً")


def split_video(input_path: str, settings: dict) -> list[dict]:
    _validate(input_path)
    speed = settings.get("speed", 1.1)
    split_min = settings.get("split", 10)
    has_audio = _has_audio(input_path)
    split_sec = split_min * 60
    parts = []

    r = subprocess.run([
        "ffprobe", "-i", input_path,
        "-show_entries", "format=duration",
        "-v", "quiet", "-of", "csv=p=0"
    ], capture_output=True, text=True)
    total_dur = float(r.stdout.strip() or 0)

    seg_starts = list(range(0, int(total_dur), split_sec - OVERLAP))
    if seg_starts and total_dur - seg_starts[-1] < MIN_LAST_SEGMENT and len(seg_starts) > 1:
        seg_starts.pop()

    os.makedirs(TEMP_DIR, exist_ok=True)

    for idx, start in enumerate(seg_starts):
        duration = split_sec
        if idx == len(seg_starts) - 1:
            duration = total_dur - start

        out = os.path.join(TEMP_DIR, f"part_{idx+1:03d}.mp4")
        filter_str = f"[0:v]setpts=PTS/{speed},scale=min(1080\\,iw):min(1920\\,ih):force_original_aspect_ratio=decrease[v]"
        if has_audio:
            filter_str += f";[0:a]atempo={speed}[a]"
        cmd = [
            "ffmpeg", "-i", input_path,
            "-ss", str(start),
            "-t", str(duration),
            "-filter_complex", filter_str,
            "-map", "[v]",
        ]
        if has_audio:
            cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", "128k", "-ar", "44100"]
        cmd += [
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-movflags", "+faststart",
            "-avoid_negative_ts", "make_zero",
            "-y", out,
        ]

        logger.info("FFmpeg part %d/%d: start=%ds dur=%ds", idx+1, len(seg_starts), start, duration)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            raise Exception(f"FFmpeg فشل في الجزء {idx+1}: {r.stderr[:500]}")

        parts.append({
            "index": idx + 1,
            "path": out,
            "start_time": start,
            "duration": duration,
        })

    logger.info("Split complete: %d parts from %s", len(parts), input_path)
    return parts

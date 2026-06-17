import base64
import logging
import os
import pickle
import sys

from config import LOG_LEVEL

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)


def decode_b64_env(key: str, output_path: str) -> None:
    raw = os.environ.get(key, "")
    if not raw:
        logger.warning("%s not set, skipping", key)
        return
    try:
        data = base64.b64decode(raw)
        with open(output_path, "wb") as f:
            f.write(data)
        logger.info("Decoded %s -> %s (%d bytes)", key, output_path, len(data))
    except Exception as exc:
        logger.error("Failed to decode %s: %s", key, exc)


def verify_token_pickle(path: str) -> bool:
    if not os.path.exists(path):
        logger.warning("token.pickle not found at %s", path)
        return False
    try:
        with open(path, "rb") as f:
            pickle.load(f)
        logger.info("token.pickle is valid")
        return True
    except Exception as exc:
        logger.error("token.pickle is corrupted: %s", exc)
        return False


def main():
    os.makedirs("data", exist_ok=True)
    os.makedirs("temp_videos", exist_ok=True)

    decode_b64_env("GOOGLE_CREDENTIALS_B64", "data/credentials.json")
    decode_b64_env("TOKEN_PICKLE_B64", "data/token.pickle")
    decode_b64_env("YT_COOKIES_B64", "data/cookies.txt")

    if not verify_token_pickle("data/token.pickle"):
        logger.error("token.pickle is invalid or missing. Re-encode from env TOKEN_PICKLE_B64.")

    logger.info("Startup checks passed, launching main...")
    import asyncio
    from main import run
    asyncio.run(run())


if __name__ == "__main__":
    main()

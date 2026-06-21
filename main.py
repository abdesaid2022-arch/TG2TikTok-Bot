import asyncio
import logging

from telegram.ext import Application

from config import USER_BOT_TOKEN, ADMIN_BOT_TOKEN
from downloader import update_ytdlp
from user_bot import build_user_app
from admin_bot import build_admin_app

logger = logging.getLogger(__name__)


async def run():
    await update_ytdlp()

    user_app = build_user_app()
    admin_app = build_admin_app()

    async with user_app:
        await user_app.start()
        await user_app.updater.start_polling()
        logger.info("User bot polling started")

        async with admin_app:
            await admin_app.start()
            await admin_app.updater.start_polling()
            logger.info("Admin bot polling started")

            try:
                await asyncio.Event().wait()
            finally:
                logger.info("Shutting down...")
                await admin_app.updater.stop()
                await admin_app.stop()
        await user_app.updater.stop()
        await user_app.stop()

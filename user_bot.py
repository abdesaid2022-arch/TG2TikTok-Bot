import asyncio
import logging
import os
import shutil

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, filters, CallbackContext)

import database as db
import queue_manager as qm
from config import USER_BOT_TOKEN, TEMP_DIR
from downloader import is_valid_youtube_url, get_video_info, download_video
from splitter import split_video
from uploader import upload_all_parts
from webhook import send_to_woopsocial
from i18n import t, get_lang
from keyboards import (main_menu, settings_keyboard, speed_buttons,
                       split_buttons, schedule_buttons)

logger = logging.getLogger(__name__)

_active_processors: dict[int, asyncio.Task] = {}


async def start(update: Update, _ctx: CallbackContext) -> None:
    user = db.get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text(t("not_registered"))
        return
    ok, reason = db.is_active(user["user_id"])
    if not ok:
        await update.message.reply_text(t(reason, get_lang(user)))
        return
    await update.message.reply_text(
        t("welcome", get_lang(user)),
        reply_markup=main_menu(user)
    )


async def queue_cmd(update: Update, _ctx: CallbackContext) -> None:
    uid = update.effective_user.id
    user = db.get_user(uid)
    L = get_lang(user)
    items = qm.get_user_queue(uid)
    current = qm.get_current(uid)
    if not items and not current:
        await update.message.reply_text(t("queue_empty", L))
        return
    lines = []
    if current:
        lines.append(f"⚙️ {current['url'][:60]} — {t('processing', L)}")
    for item in items:
        pos = qm.get_position(uid, item["id"])
        lines.append(f"{pos}. {item['url'][:60]} — ID: {item['id']}")
    await update.message.reply_text("\n".join(lines))


async def cancel_cmd(update: Update, _ctx: CallbackContext) -> None:
    uid = update.effective_user.id
    user = db.get_user(uid)
    L = get_lang(user)
    args = update.message.text.split(maxsplit=1)
    if len(args) < 2:
        items = qm.get_user_queue(uid)
        if not items:
            await update.message.reply_text(t("queue_empty", L))
            return
        await update.message.reply_text(
            f"أرسل /cancel ID\nالأيدي المتاحة: " + ", ".join(it["id"] for it in items))
        return
    ok = qm.cancel_item(uid, args[1])
    await update.message.reply_text(t("cancelled" if ok else "not_found", L))


async def schedule_cmd(update: Update, _ctx: CallbackContext) -> None:
    uid = update.effective_user.id
    user = db.get_user(uid)
    if not user:
        await update.message.reply_text(t("not_registered"))
        return
    L = get_lang(user)
    last = user.get("last_slot")
    if not last:
        await update.message.reply_text("لا توجد مواعيد نشر مجدولة", reply_markup=main_menu(user))
        return
    items = qm.get_user_queue(uid)
    pending_count = len(items)
    sched = user["settings"].get("schedule", 15)
    await update.message.reply_text(
        f"آخر نشر مجدول: {last[:19]}\n"
        f"فاصل النشر: {sched} دقيقة\n"
        f"فيديو في الانتظار: {pending_count}",
        reply_markup=main_menu(user))


async def handle_link(update: Update, _ctx: CallbackContext) -> None:
    uid = update.effective_user.id
    user = db.get_user(uid)
    if not user:
        await update.message.reply_text(t("not_registered"))
        return
    L = get_lang(user)
    ok, reason = db.is_active(uid)
    if not ok:
        await update.message.reply_text(t(reason, L))
        return

    url = update.message.text.strip()
    if not is_valid_youtube_url(url):
        await update.message.reply_text(t("invalid_url", L))
        return

    msg = await update.message.reply_text(t("checking", L))
    try:
        info = get_video_info(url)
    except Exception as exc:
        await msg.edit_text(f"❌ {exc}")
        return

    try:
        item = qm.add_to_queue(uid, url, user["settings"])
    except Exception as exc:
        err_key = str(exc)
        await msg.edit_text(t(err_key, L))
        return

    minutes = info["duration"] // 60
    await msg.edit_text(
        t("video_info", L).format(title=info["title"][:50], duration=f"{minutes}د",
                                  position=qm.get_position(uid, item["id"]))
        + f"\n\n{t('added_to_queue', L)}"
        + f"\n🆔 {item['id']}",
        reply_markup=main_menu(user))

    if uid not in _active_processors or _active_processors[uid].done():
        _active_processors[uid] = asyncio.create_task(process_queue(uid, update.get_bot()))


async def process_queue(user_id: int, bot) -> None:
    loop = asyncio.get_event_loop()
    while True:
        item = qm.get_current(user_id)
        if not item:
            items = qm.get_user_queue(user_id)
            if not items:
                return
            item = items[0]
            qm.start_processing(user_id, item["id"])

        user = db.get_user(user_id)
        L = get_lang(user)
        try:
            await bot.send_message(user_id,
                f"⚙️ {t('processing', L)}: {item['url'][:60]}")

            path = await loop.run_in_executor(None, download_video, item["url"], item["id"])
            parts = await loop.run_in_executor(None, split_video, path, item["settings"])
            title = get_video_info(item["url"])["title"]
            drive_data = await loop.run_in_executor(None, upload_all_parts, user_id, parts, title)

            u = db.get_user(user_id)
            result = await loop.run_in_executor(
                None, send_to_woopsocial, user_id, drive_data, title,
                item["settings"]["schedule"] * 60,
                u["woopsocial_api_key"], u["woopsocial_project_id"],
                u["woopsocial_social_account_id"])

            ok_parts = sum(1 for r in result if r["status"] == "ok")
            await bot.send_message(user_id,
                f"✅ تمت معالجة {item['url'][:50]} → {ok_parts}/{len(parts)} أجزاء")

        except Exception as exc:
            err = str(exc)
            if err == "cookies_expired":
                err = t("cookies_expired", get_lang(user))
            await bot.send_message(user_id, f"❌ {err[:400]}")
        finally:
            qm.finish_processing(user_id, item["id"])
            try:
                for f in os.listdir(TEMP_DIR):
                    fp = os.path.join(TEMP_DIR, f)
                    if os.path.isfile(fp):
                        os.remove(fp)
            except Exception:
                pass


async def menu_callback(update: Update, ctx: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    user = db.get_user(uid)
    if not user:
        await query.edit_message_text(t("not_registered"))
        return
    L = get_lang(user)
    data = query.data

    if data == "main_menu":
        await query.edit_message_text(t("welcome", L), reply_markup=main_menu(user))

    elif data == "settings":
        await query.edit_message_text(t("current_settings", L), reply_markup=settings_keyboard(user))

    elif data == "settings_speed":
        await query.edit_message_text(t("speed", L), reply_markup=speed_buttons(user))

    elif data.startswith("set_speed_"):
        val = float(data.split("_")[2])
        db.update_user(uid, {"settings": {"speed": val}})
        user = db.get_user(uid)
        await query.edit_message_text(t("settings_updated", L), reply_markup=settings_keyboard(user))

    elif data == "settings_split":
        await query.edit_message_text(t("split_duration", L), reply_markup=split_buttons(user))

    elif data.startswith("set_split_"):
        val = int(data.split("_")[2])
        db.update_user(uid, {"settings": {"split": val}})
        user = db.get_user(uid)
        await query.edit_message_text(t("settings_updated", L), reply_markup=settings_keyboard(user))

    elif data == "settings_schedule":
        await query.edit_message_text(t("schedule_interval", L), reply_markup=schedule_buttons(user))

    elif data.startswith("set_schedule_"):
        val = int(data.split("_")[2])
        db.update_user(uid, {"settings": {"schedule": val}})
        user = db.get_user(uid)
        await query.edit_message_text(t("settings_updated", L), reply_markup=settings_keyboard(user))

    elif data == "queue":
        items = qm.get_user_queue(uid)
        current = qm.get_current(uid)
        if not items and not current:
            await query.edit_message_text(t("queue_empty", L), reply_markup=main_menu(user))
            return
        lines = []
        if current:
            lines.append(f"⚙️ {current['url'][:60]} — {t('processing', L)}")
        for item in items:
            pos = qm.get_position(uid, item["id"])
            lines.append(f"{pos}. {item['url'][:60]} — ID: {item['id']}")
        await query.edit_message_text("\n".join(lines), reply_markup=main_menu(user))

    elif data == "account":
        expires = user.get("expires_at", "?")[:10]
        await query.edit_message_text(
            f"🆔 {uid}\n"
            f"{t('plan', L)}: {user.get('plan')}\n"
            f"{t('status', L)}: {t(user.get('status','active'), L)}\n"
            f"انتهاء: {expires}\n"
            f"فيديوهات: {user.get('stats',{}).get('total_videos',0)}",
            reply_markup=main_menu(user))

    elif data == "schedule":
        last = user.get("last_slot")
        if not last:
            await query.edit_message_text("لا توجد مواعيد نشر", reply_markup=main_menu(user))
            return
        sched = user["settings"].get("schedule", 15)
        pending = len(qm.get_user_queue(uid))
        await query.edit_message_text(
            f"آخر نشر: {last[:19]}\nالفاصل: {sched}د\nبالانتظار: {pending}",
            reply_markup=main_menu(user))

    elif data == "help":
        await query.edit_message_text(
            "أرسل رابط يوتيوب → المعالجة التلقائية → النشر على تيكتوك\n"
            "الأوامر:\n"
            "/queue — طابوري\n"
            "/cancel ID — إلغاء\n"
            "/schedule — جدول النشر",
            reply_markup=main_menu(user))


def build_user_app() -> Application:
    app = Application.builder().token(USER_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("queue", queue_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("schedule", schedule_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(menu_callback))
    return app

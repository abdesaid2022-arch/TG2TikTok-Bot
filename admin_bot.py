import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          MessageHandler, filters, ConversationHandler,
                          CallbackContext)

import database as db
from config import ADMIN_BOT_TOKEN, ADMIN_ID
from keyboards import admin_menu, user_actions, plan_buttons, confirm_delete

logger = logging.getLogger(__name__)

ADD_USER_ID, ADD_PLAN, ADD_DAYS, ADD_API, ADD_PROJECT, ADD_SOCIAL = range(6)
ADDDAYS_AMOUNT, BROADCAST_MSG, SEARCH_ID = range(6, 9)


async def admin_start(update: Update, _ctx: CallbackContext) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ غير مصرح")
        return
    await update.message.reply_text("👑 لوحة الإدارة", reply_markup=admin_menu())


# ── Add user conversation entry ──
async def add_user_entry(update: Update, _ctx: CallbackContext) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("أدخل user_id:")
    return ADD_USER_ID


async def add_user_id(update: Update, ctx: CallbackContext) -> int:
    ctx.user_data["add_uid"] = int(update.message.text.strip())
    await update.message.reply_text("اختر الخطة:",
        reply_markup=plan_buttons(0))
    return ADD_PLAN


async def add_user_plan(update: Update, ctx: CallbackContext) -> int:
    parts = update.callback_query.data.split("_")
    ctx.user_data["add_plan"] = parts[-1]
    await update.callback_query.edit_message_text("أدخل عدد الأيام:")
    return ADD_DAYS


async def add_user_days(update: Update, ctx: CallbackContext) -> int:
    ctx.user_data["add_days"] = int(update.message.text.strip())
    await update.message.reply_text("أدخل WoopSocial API Key:")
    return ADD_API


async def add_user_api(update: Update, ctx: CallbackContext) -> int:
    ctx.user_data["add_api"] = update.message.text.strip()
    await update.message.reply_text("أدخل Project ID:")
    return ADD_PROJECT


async def add_user_project(update: Update, ctx: CallbackContext) -> int:
    ctx.user_data["add_project"] = update.message.text.strip()
    await update.message.reply_text("أدخل Social Account ID:")
    return ADD_SOCIAL


async def add_user_social(update: Update, ctx: CallbackContext) -> int:
    ctx.user_data["add_social"] = update.message.text.strip()
    d = ctx.user_data
    user = db.add_user(d["add_uid"], d["add_plan"], d["add_days"],
                       d["add_api"], d["add_project"], d["add_social"])
    await update.message.reply_text(
        f"✅ تم إنشاء المستخدم {d['add_uid']}\n"
        f"الخطة: {d['add_plan']}\nالأيام: {d['add_days']}")
    try:
        await update.get_bot().send_message(d["add_uid"], "✅ تم تفعيل اشتراكك!")
    except Exception as exc:
        await update.message.reply_text(f"ملاحظة: لم يستطع البوت مراسلة المستخدم: {exc}")
    ctx.user_data.clear()
    return ConversationHandler.END


# ── Add days conversation entry ──
async def adddays_entry(update: Update, ctx: CallbackContext) -> int:
    await update.callback_query.answer()
    uid = int(update.callback_query.data.split("_")[2])
    ctx.user_data["adddays_uid"] = uid
    await update.callback_query.edit_message_text("أدخل عدد الأيام:")
    return ADDDAYS_AMOUNT


async def adddays_amount(update: Update, ctx: CallbackContext) -> int:
    uid = ctx.user_data["adddays_uid"]
    days = int(update.message.text.strip())
    db.add_days(uid, days)
    await update.message.reply_text(f"✅ تم إضافة {days} يوم للمستخدم {uid}")
    ctx.user_data.clear()
    return ConversationHandler.END


# ── Broadcast conversation entry ──
async def broadcast_entry(update: Update, _ctx: CallbackContext) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("أدخل الرسالة للبث:")
    return BROADCAST_MSG


async def broadcast_send(update: Update, ctx: CallbackContext) -> int:
    text = update.message.text
    users = db.get_all_users()
    ok = fail = 0
    for u in users:
        if u["status"] != "active":
            continue
        try:
            await update.get_bot().send_message(u["user_id"], text)
            ok += 1
        except Exception:
            fail += 1
    await update.message.reply_text(f"✅ البث تم: {ok} نجاح، {fail} فشل")
    ctx.user_data.clear()
    return ConversationHandler.END


# ── Search conversation entry ──
async def search_entry(update: Update, _ctx: CallbackContext) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("أدخل user_id للبحث:")
    return SEARCH_ID


async def search_result(update: Update, _ctx: CallbackContext) -> int:
    uid = int(update.message.text.strip())
    user = db.get_user(uid)
    if not user:
        await update.message.reply_text("❌ المستخدم غير موجود")
        return ConversationHandler.END
    await update.message.reply_text(
        f"🆔 {uid}\n"
        f"المستخدم: {user.get('username','')}\n"
        f"الخطة: {user.get('plan')}\n"
        f"الحالة: {user.get('status')}\n"
        f"انتهاء: {user.get('expires_at','?')[:10]}",
        reply_markup=user_actions(uid))
    return ConversationHandler.END


# ── General admin callbacks (non-conversation) ──
async def admin_callback(update: Update, _ctx: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "admin_list_users":
        users = db.get_all_users()
        if not users:
            await query.edit_message_text("لا يوجد مستخدمين")
            return
        kb = [[InlineKeyboardButton(
            f"{u.get('user_id')} — {u.get('plan')} — {u.get('status')}",
            callback_data=f"admin_userstats_{u['user_id']}")] for u in users]
        kb.append([InlineKeyboardButton("← رجوع", callback_data="admin_back")])
        await query.edit_message_text("📋 قائمة المستخدمين:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("admin_userstats_"):
        uid = int(data.split("_")[2])
        user = db.get_user(uid)
        if not user:
            await query.edit_message_text("❌ غير موجود")
            return
        await query.edit_message_text(
            f"🆔 {uid}\n"
            f"👤 {user.get('username','')}\n"
            f"📋 {user.get('plan')} — {user.get('status')}\n"
            f"📅 انتهاء: {user.get('expires_at','?')[:10]}\n"
            f"🎬 فيديوهات: {user.get('stats',{}).get('total_videos',0)}",
            reply_markup=user_actions(uid))

    elif data.startswith("admin_suspend_"):
        uid = int(data.split("_")[2])
        db.set_user_status(uid, "suspended")
        await query.edit_message_text(f"✅ تم إيقاف {uid}")

    elif data.startswith("admin_activate_"):
        uid = int(data.split("_")[2])
        db.set_user_status(uid, "active")
        await query.edit_message_text(f"✅ تم تفعيل {uid}")

    elif data.startswith("admin_delete_"):
        uid = int(data.split("_")[2])
        await query.edit_message_text(f"تأكيد حذف {uid}?", reply_markup=confirm_delete(uid))

    elif data.startswith("admin_confirm_delete_"):
        uid = int(data.split("_")[3])
        db.delete_user(uid)
        await query.edit_message_text(f"✅ تم حذف {uid}")

    elif data.startswith("admin_change_plan_"):
        uid = int(data.split("_")[3])
        await query.edit_message_text("اختر الخطة:", reply_markup=plan_buttons(uid))

    elif data.startswith("admin_set_plan_"):
        parts = data.split("_")
        uid = int(parts[3])
        plan = parts[4]
        if uid != 0:
            db.change_plan(uid, plan)
            await query.edit_message_text(f"✅ تم تغيير خطة {uid} إلى {plan}")
        else:
            await query.edit_message_text("❌ لا يمكن تغيير خطة المستخدم 0")

    elif data.startswith("admin_change_lang_"):
        uid = int(data.split("_")[3])
        user = db.get_user(uid)
        new_lang = "en" if user.get("language") == "ar" else "ar"
        db.update_user(uid, {"language": new_lang})
        await query.edit_message_text(f"✅ تم تغيير لغة {uid} إلى {new_lang}")

    elif data == "admin_stats":
        s = db.get_stats_summary()
        await query.edit_message_text(
            f"📊 الإحصائيات:\n"
            f"الإجمالي: {s['total']}\n"
            f"نشط: {s['active']}\n"
            f"موقوف: {s['suspended']}\n"
            f"منتهي: {s['expired']}\n"
            f"تجريبي: {s['trial']}")

    elif data == "admin_back":
        await query.edit_message_text("👑 لوحة الإدارة", reply_markup=admin_menu())


def build_admin_app() -> Application:
    app = Application.builder().token(ADMIN_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", admin_start))

    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_user_entry, pattern="^admin_add_user$"),
            CallbackQueryHandler(adddays_entry, pattern="^admin_adddays_\\d+$"),
            CallbackQueryHandler(broadcast_entry, pattern="^admin_broadcast$"),
            CallbackQueryHandler(search_entry, pattern="^admin_search$"),
        ],
        states={
            ADD_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_user_id)],
            ADD_PLAN: [CallbackQueryHandler(add_user_plan, pattern="^admin_set_plan_0_")],
            ADD_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_user_days)],
            ADD_API: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_user_api)],
            ADD_PROJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_user_project)],
            ADD_SOCIAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_user_social)],
            ADDDAYS_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, adddays_amount)],
            BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)],
            SEARCH_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_result)],
        },
        fallbacks=[CommandHandler("start", admin_start)],
        per_chat=True,
        per_user=True,
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    return app

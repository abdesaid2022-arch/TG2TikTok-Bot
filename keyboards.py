from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from i18n import t, get_lang


def main_menu(user: dict) -> InlineKeyboardMarkup:
    L = get_lang(user)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("menu", L), callback_data="settings"),
         InlineKeyboardButton(t("my_queue", L), callback_data="queue")],
        [InlineKeyboardButton(t("my_account", L), callback_data="account"),
         InlineKeyboardButton(t("my_schedule", L), callback_data="schedule")],
        [InlineKeyboardButton(t("help", L), callback_data="help")],
    ])


def settings_keyboard(user: dict) -> InlineKeyboardMarkup:
    L = get_lang(user)
    s = user.get("settings", {})
    speed = s.get("speed", 1.1)
    split = s.get("split", 10)
    schedule = s.get("schedule", 15)
    spd_opts = [0.75, 1.0, 1.1, 1.25, 1.5]
    spl_opts = [3, 5, 10, 15, 30]
    sch_opts = [5, 10, 15, 30, 60]
    buttons = [
        [InlineKeyboardButton(
            f'{t("speed", L)}: {" ".join(f"【{v}x】" if v == speed else f"{v}x" for v in spd_opts)}',
            callback_data="settings_speed")],
        [InlineKeyboardButton(
            f'{t("split_duration", L)}: {" ".join(f"【{v}د】" if v == split else f"{v}د" for v in spl_opts)}',
            callback_data="settings_split")],
        [InlineKeyboardButton(
            f'{t("schedule_interval", L)}: {" ".join(f"【{v}د】" if v == schedule else f"{v}د" for v in sch_opts)}',
            callback_data="settings_schedule")],
        [InlineKeyboardButton(t("back", L), callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(buttons)


def speed_buttons(user: dict) -> InlineKeyboardMarkup:
    L = get_lang(user)
    cur = user.get("settings", {}).get("speed", 1.1)
    speeds = [0.75, 1.0, 1.1, 1.25, 1.5]
    row = [InlineKeyboardButton(f'{"【" if v==cur else ""}{v}x{"】" if v==cur else ""}',
                                callback_data=f"set_speed_{v}") for v in speeds]
    row.append(InlineKeyboardButton(t("back", L), callback_data="settings"))
    return InlineKeyboardMarkup([row])


def split_buttons(user: dict) -> InlineKeyboardMarkup:
    L = get_lang(user)
    cur = user.get("settings", {}).get("split", 10)
    splits = [3, 5, 10, 15, 30]
    row = [InlineKeyboardButton(f'{"【" if v==cur else ""}{v}د{"】" if v==cur else ""}',
                                callback_data=f"set_split_{v}") for v in splits]
    row.append(InlineKeyboardButton(t("back", L), callback_data="settings"))
    return InlineKeyboardMarkup([row])


def schedule_buttons(user: dict) -> InlineKeyboardMarkup:
    L = get_lang(user)
    cur = user.get("settings", {}).get("schedule", 15)
    schedules = [5, 10, 15, 30, 60]
    row = [InlineKeyboardButton(f'{"【" if v==cur else ""}{v}د{"】" if v==cur else ""}',
                                callback_data=f"set_schedule_{v}") for v in schedules]
    row.append(InlineKeyboardButton(t("back", L), callback_data="settings"))
    return InlineKeyboardMarkup([row])


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة مستخدم", callback_data="admin_add_user"),
         InlineKeyboardButton("📋 قائمة المستخدمين", callback_data="admin_list_users")],
        [InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats"),
         InlineKeyboardButton("🔍 بحث عن مستخدم", callback_data="admin_search")],
        [InlineKeyboardButton("📢 بث رسالة", callback_data="admin_broadcast")],
    ])


def user_actions(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("إيقاف", callback_data=f"admin_suspend_{user_id}"),
         InlineKeyboardButton("تفعيل", callback_data=f"admin_activate_{user_id}")],
        [InlineKeyboardButton("تغيير الخطة", callback_data=f"admin_change_plan_{user_id}"),
         InlineKeyboardButton("إضافة أيام", callback_data=f"admin_adddays_{user_id}")],
        [InlineKeyboardButton("تبديل اللغة", callback_data=f"admin_change_lang_{user_id}"),
         InlineKeyboardButton("حذف", callback_data=f"admin_delete_{user_id}")],
        [InlineKeyboardButton("← رجوع", callback_data="admin_list_users")],
    ])


def plan_buttons(user_id: int) -> InlineKeyboardMarkup:
    plans = [("trial", "تجريبي"), ("basic", "أساسي"),
             ("pro", "احترافي"), ("unlimited", "غير محدود")]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(name, callback_data=f"admin_set_plan_{user_id}_{key}")]
        for key, name in plans
    ])


def confirm_delete(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأكيد الحذف", callback_data=f"admin_confirm_delete_{user_id}"),
         InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")],
    ])

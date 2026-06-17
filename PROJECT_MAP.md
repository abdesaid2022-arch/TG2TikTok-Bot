# TG2TikTok Bot — Project Map

## TECH_STACK

| طبقة | التقنية | الإصدار | ملاحظات |
|------|---------|---------|---------|
| لغة | Python | 3.13+ | f-strings, zoneinfo, dataclasses |
| بوت تيليغرام | python-telegram-bot | 22.8 | `Application` async context manager, `ConversationHandler` with `per_chat=True, per_user=True` |
| تحميل فيديو | yt-dlp | 2026.6.9 | player_clients: ios → android → mweb, PO Token support |
| معالجة فيديو | FFmpeg (عبر static-ffmpeg) | 3.0 | `-ss` بعد `-i` إلزامي، تداخل 5 ثوان، audio check مع حذف `-c:a` عند عدم وجود صوت |
| رفع | Google Drive API v3 (google-api-python-client) | 2.197.0 | resumable upload, chunks 5MB, 3 retries, public permissions |
| جدولة نشر | WoopSocial REST API | v1 | POST /posts, Bearer token, last_slot tracking |
| تخزين | `data/users_db.json` | — | `threading.Lock()` لكل وصول، JSON file per user |
| تشغيل | asyncio + run_in_executor | — | عمليات ثقيلة (yt-dlp, FFmpeg, Drive) خارج الـ event loop |
| سحب | Railway (مستهدف) | — | env vars base64, start.py نقطة الدخول |

## SYSTEM_FLOW

```
📱 مستخدم → رابط يوتيوب
     ↓
🔄 user_bot.py: database.is_active() → تحقق تسجيل + صلاحية
     ↓
🔍 downloader.get_video_info() → عنوان + مدة
     ↓
📋 queue_manager.add_to_queue() → تحقق max_queue + daily_limit
     ↓
⚙️ asyncio.create_task(process_queue()) ← لكل مستخدم بشكل مستقل
     ↓
   ┌─ loop.run_in_executor(None, ...) ──────────────────┐
   │                                                     │
   │  1. downloader.download_video()  → yt-dlp → mp4    │
   │  2. splitter.split_video()       → FFmpeg → أجزاء  │
   │  3. uploader.upload_all_parts()  → Drive → URLs    │
   │  4. webhook.send_to_woopsocial() → WoopSocial POST │
   │  5. drive_cleaner.schedule_deletion() → حذف لاحق   │
   └─────────────────────────────────────────────────────┘
     ↓
📨 user_bot: إشعار اكتمال + عدد الأجزاء
```

**تدفق بوت الإدارة:**
```
👑 admin_bot.py ← ADMIN_ID حصري
     ↓
➕ إضافة مستخدم → ConversationHandler (6 خطوات: id, plan, days, api_key, project, social)
📋 قائمة مستخدمين → InlineKeyboard → admin_userstats_{id} → إجراءات (إيقاف/تفعيل/حذف/تغيير خطة/إضافة أيام/لغة)
📊 إحصائيات → database.get_stats_summary()
📢 بث → ConversationHandler → إرسال لكل active → تقرير نجاح/فشل
🔍 بحث → ConversationHandler → عرض تفاصيل
```

## ARCHITECTURE

```
start.py                     # يفك base64 env → يتحقق pickle → asyncio.run(main())
└── main.py                  # async with user_app → start_polling() + admin_app → start_polling()
    ├── config.py            # env vars, PLANS, ثوابت
    ├── database.py          # JSON CRUD + threading.Lock() + 9 دوال
    ├── i18n.py              # TRANSLATIONS dict + t(key, lang) + get_lang(user)
    ├── user_bot.py          # Application + 4 Commands + link handler + process_queue + CallbackQuery
    ├── admin_bot.py         # Application + 1 Command + 1 ConversationHandler (4 entry points) + 1 CallbackHandler
    ├── keyboards.py         # 10 دوال بناء InlineKeyboardMarkup (خالصة)
    ├── queue_manager.py     # طابور في memory لكل user + Lock + 9 دوال
    ├── downloader.py        # yt-dlp: update, validate, info, download + client rotation + PO Token
    ├── splitter.py          # FFmpeg: validate, has_audio, split_video + overlap + audio check
    ├── uploader.py          # Google Drive: get_service, create_folder, upload_part (3 retries), public, schedule_deletion
    ├── webhook.py           # WoopSocial: send_to_woopsocial (3 retries) + last_slot tracking
    ├── drive_cleaner.py     # Background thread loop: cleanup batch every 30s, daemon
    └── data/
        ├── users_db.json    # ملف JSON واحد
        ├── token.pickle     # Google OAuth (يُبنى من env)
        └── cookies.txt      # يوتيوب cookies (اختياري، يُبنى من env)
```

## ORPHANS & PENDING

| النقص | الأولوية | التعليق |
|-------|----------|---------|
| **اختبارات تحميل ثقيل** | متوسطة | 3 مستخدمين كل منهم 10 فيديوهات في نفس الوقت — يحتاج بيئة اختبار بفيديوهات حقيقية (yt-dlp + FFmpeg + Drive) |
| **Graceful shutdown للـ process_queue tasks** | منخفضة | عند إيقاف البوت، الـ asyncio tasks تُلغى. يمكن إضافة `asyncio.shield()` أو حفظ state في database |

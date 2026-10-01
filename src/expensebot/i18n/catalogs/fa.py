"""Persian message catalog.

Keys mirror the English catalog exactly; parity is enforced by a test. Dates and
chart labels remain Gregorian and English by project decision, so no month
translation is used for charts.
"""

MESSAGES: dict[str, str] = {
    # onboarding
    "welcome": (
        "👋 به ربات مدیریت هزینه خوش آمدید.\n\n"
        "کافی است مبلغ و توضیح را بفرستید، مثلاً <code>۲۵۰۰۰ ناهار</code>، "
        "تا از شما بپرسم در کدام دسته ثبت شود.\n\n"
        "برای دیدن همه امکانات /help را بزنید."
    ),
    "help": (
        "<b>دستورها</b>\n"
        "/add — ثبت هزینه\n"
        "/list — مرور و ویرایش هزینه‌های اخیر\n"
        "/report — خلاصه و نمودار این ماه\n"
        "/categories — مدیریت دسته‌ها\n"
        "/export — دریافت خروجی CSV\n"
        "/remind — یادآور روزانه ثبت هزینه\n"
        "/language — تغییر زبان\n"
        "/settings — نمایش تنظیمات\n\n"
        "<b>نکته</b>: می‌توانید /add را ننویسید و مستقیم "
        "<code>۲۵۰۰۰ ناهار</code> بفرستید."
    ),
    "settings_title": "<b>تنظیمات</b>",
    "settings_language": "زبان: {value}",
    "settings_timezone": "منطقه زمانی: {value}",
    "settings_currency": "واحد پول: {value}",
    "settings_reminder_on": "یادآور روزانه: {value}",
    "settings_reminder_off": "یادآور روزانه: خاموش",
    # language
    "choose_language": "زبان خود را انتخاب کنید:",
    "language_changed": "زبان روی فارسی تنظیم شد.",
    # adding expenses
    "ask_category": "{amount}{note}\nکدام دسته؟",
    "expense_saved": "✅ {amount} در دسته {category} ثبت شد.",
    "expense_note_suffix": " — {note}",
    "parse_failed": (
        "نتوانستم مبلغی در پیام شما پیدا کنم.\n" "چیزی مثل <code>۲۵۰۰۰ ناهار</code> بفرستید."
    ),
    "amount_too_large": "این مبلغ بیش از حد بزرگ به نظر می‌رسد.",
    "amount_must_be_positive": "مبلغ باید بزرگ‌تر از صفر باشد.",
    "note_too_long": "توضیح خیلی طولانی است — کمتر از {limit} نویسه بنویسید.",
    # listing
    "list_empty": "هنوز هزینه‌ای ثبت نشده است.",
    "list_title": "<b>هزینه‌های اخیر</b> (صفحه {page} از {pages})",
    "list_row": "{index}. {date} · {category} · {amount}{note}",
    "expense_detail": (
        "<b>هزینه</b>\n" "مبلغ: {amount}\n" "دسته: {category}\n" "تاریخ: {date}\n" "توضیح: {note}"
    ),
    "expense_deleted": "🗑 هزینه حذف شد.",
    "expense_updated": "✏️ هزینه به‌روزرسانی شد.",
    "ask_new_amount": "مبلغ جدید را بفرستید.",
    "ask_new_note": "توضیح جدید را بفرستید.",
    "none": "—",
    # categories
    "categories_title": "<b>دسته‌های شما</b>",
    "category_added": "✅ دسته {category} اضافه شد.",
    "category_renamed": "✏️ به {category} تغییر نام یافت.",
    "category_deleted": "🗑 دسته حذف شد. هزینه‌های آن حفظ شدند.",
    "category_builtin_hidden": "دسته پنهان شد. دسته‌های پیش‌فرض حذف‌شدنی نیستند.",
    "ask_category_name": "نام دسته چه باشد؟",
    "ask_category_emoji": "یک ایموجی برای آن بفرستید، یا /skip را بزنید.",
    "category_exists": "دسته‌ای با این نام از قبل دارید.",
    "category_limit": "به حداکثر {limit} دسته رسیده‌اید.",
    # reports
    "report_title": "<b>{month}</b>",
    "report_total": "مجموع: {amount}",
    "report_empty": "برای {month} چیزی ثبت نشده است.",
    "report_row": "{emoji} {name} — {amount} ({percent}٪)",
    "report_vs_previous_up": "📈 {percent}٪ بیشتر از {month}",
    "report_vs_previous_down": "📉 {percent}٪ کمتر از {month}",
    "report_vs_previous_same": "برابر با {month}",
    "report_no_previous": "برای {month} داده‌ای نیست.",
    # export
    "export_caption": "هزینه‌های شما ({count} ردیف).",
    "export_empty": "هنوز چیزی برای خروجی گرفتن نیست.",
    "csv_date": "تاریخ",
    "csv_amount": "مبلغ",
    "csv_currency": "واحد پول",
    "csv_category": "دسته",
    "csv_note": "توضیح",
    # reminders
    "reminder_set": "⏰ هر روز ساعت {time} یادآوری می‌کنم.",
    "reminder_cleared": "یادآور روزانه خاموش شد.",
    "reminder_usage": (
        "برای تنظیم زمان <code>/remind 21:30</code> و برای خاموش کردن "
        "<code>/remind off</code> را بزنید."
    ),
    "reminder_bad_time": "زمان معتبر نیست. قالب ۲۴ ساعته مثل <code>21:30</code> بنویسید.",
    "reminder_nudge": "🌙 امروز هیچ هزینه‌ای ثبت نکرده‌اید.",
    # buttons
    "btn_prev": "‹ قبلی",
    "btn_next": "بعدی ›",
    "btn_back": "‹ بازگشت",
    "btn_undo": "برگردان",
    "btn_delete": "حذف",
    "btn_edit_amount": "ویرایش مبلغ",
    "btn_edit_note": "ویرایش توضیح",
    "btn_change_category": "تغییر دسته",
    "btn_add_category": "➕ دسته جدید",
    "btn_rename": "تغییر نام",
    "btn_cancel": "انصراف",
    "btn_skip": "رد کردن",
    # generic
    "cancelled": "لغو شد.",
    "error_generic": "مشکلی پیش آمد. دوباره تلاش کنید.",
    "rate_limited": "بیش از حد سریع درخواست می‌دهید. کمی بعد دوباره تلاش کنید.",
    "not_found": "دیگر نتوانستم آن را پیدا کنم.",
    "uncategorized": "بدون دسته",
    # command menu descriptions (shown by Telegram's Menu button)
    "cmd_add": "ثبت هزینه",
    "cmd_list": "مرور و ویرایش هزینه‌های اخیر",
    "cmd_report": "خلاصه و نمودار این ماه",
    "cmd_categories": "مدیریت دسته‌ها",
    "cmd_export": "دریافت خروجی CSV",
    "cmd_remind": "یادآور روزانه ثبت هزینه",
    "cmd_language": "تغییر زبان",
    "cmd_settings": "نمایش تنظیمات",
    "cmd_help": "نمایش راهنما",
    # built-in category names (keyed by slug)
    "category.food": "خوراک",
    "category.transport": "حمل‌ونقل",
    "category.housing": "مسکن",
    "category.bills": "قبض‌ها",
    "category.health": "سلامت",
    "category.shopping": "خرید",
    "category.fun": "سرگرمی",
    "category.other": "سایر",
    # month names
    "month.1": "ژانویه",
    "month.2": "فوریه",
    "month.3": "مارس",
    "month.4": "آوریل",
    "month.5": "مه",
    "month.6": "ژوئن",
    "month.7": "ژوئیه",
    "month.8": "اوت",
    "month.9": "سپتامبر",
    "month.10": "اکتبر",
    "month.11": "نوامبر",
    "month.12": "دسامبر",
}

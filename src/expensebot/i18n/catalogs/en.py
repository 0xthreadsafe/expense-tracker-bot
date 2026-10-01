"""English message catalog, and the reference key set for every other locale."""

MESSAGES: dict[str, str] = {
    # onboarding
    "welcome": (
        "👋 Welcome to the expense tracker.\n\n"
        "Just send me an amount and a note, like <code>25000 lunch</code>, "
        "and I will ask which category it belongs to.\n\n"
        "Use /help to see everything I can do."
    ),
    "help": (
        "<b>Commands</b>\n"
        "/add — record an expense\n"
        "/list — browse and edit recent expenses\n"
        "/report — this month's summary and chart\n"
        "/categories — manage your categories\n"
        "/export — download your expenses as CSV\n"
        "/remind — daily reminder to log spending\n"
        "/language — change language\n"
        "/settings — show current settings\n\n"
        "<b>Tip</b>: you can skip /add and simply send "
        "<code>25000 lunch</code>."
    ),
    "settings_title": "<b>Settings</b>",
    "settings_language": "Language: {value}",
    "settings_timezone": "Timezone: {value}",
    "settings_currency": "Currency: {value}",
    "settings_reminder_on": "Daily reminder: {value}",
    "settings_reminder_off": "Daily reminder: off",
    # language
    "choose_language": "Choose your language:",
    "language_changed": "Language set to English.",
    # adding expenses
    "ask_category": "{amount}{note}\nWhich category?",
    "expense_saved": "✅ Saved {amount} under {category}.",
    "expense_note_suffix": " — {note}",
    "parse_failed": (
        "I could not read an amount in that message.\n"
        "Try something like <code>25000 lunch</code>."
    ),
    "amount_too_large": "That amount looks too large to be real.",
    "amount_must_be_positive": "The amount has to be greater than zero.",
    "note_too_long": "That note is too long — keep it under {limit} characters.",
    # listing
    "list_empty": "No expenses recorded yet.",
    "list_title": "<b>Recent expenses</b> (page {page} of {pages})",
    "list_row": "{index}. {date} · {category} · {amount}{note}",
    "expense_detail": (
        "<b>Expense</b>\n"
        "Amount: {amount}\n"
        "Category: {category}\n"
        "Date: {date}\n"
        "Note: {note}"
    ),
    "expense_deleted": "🗑 Expense deleted.",
    "expense_updated": "✏️ Expense updated.",
    "ask_new_amount": "Send the new amount.",
    "ask_new_note": "Send the new note.",
    "none": "—",
    # categories
    "categories_title": "<b>Your categories</b>",
    "category_added": "✅ Added category {category}.",
    "category_renamed": "✏️ Renamed to {category}.",
    "category_deleted": "🗑 Category removed. Its expenses were kept.",
    "category_builtin_hidden": "Category hidden. Built-in categories cannot be deleted.",
    "ask_category_name": "What should the category be called?",
    "ask_category_emoji": "Send an emoji for it, or /skip.",
    "category_exists": "You already have a category with that name.",
    "category_limit": "You have reached the maximum of {limit} categories.",
    # reports
    "report_title": "<b>{month}</b>",
    "report_total": "Total: {amount}",
    "report_empty": "Nothing recorded for {month}.",
    "report_row": "{emoji} {name} — {amount} ({percent}%)",
    "report_vs_previous_up": "📈 {percent}% more than {month}",
    "report_vs_previous_down": "📉 {percent}% less than {month}",
    "report_vs_previous_same": "Same as {month}",
    "report_no_previous": "No data for {month}.",
    # export
    "export_caption": "Your expenses ({count} rows).",
    "export_empty": "There is nothing to export yet.",
    "csv_date": "date",
    "csv_amount": "amount",
    "csv_currency": "currency",
    "csv_category": "category",
    "csv_note": "note",
    # reminders
    "reminder_set": "⏰ I will remind you daily at {time}.",
    "reminder_cleared": "Daily reminder turned off.",
    "reminder_usage": "Use <code>/remind 21:30</code> to set a time, or <code>/remind off</code>.",
    "reminder_bad_time": "That is not a valid time. Use 24-hour format, like <code>21:30</code>.",
    "reminder_nudge": "🌙 You have not logged any spending today.",
    # buttons
    "btn_prev": "‹ Previous",
    "btn_next": "Next ›",
    "btn_back": "‹ Back",
    "btn_undo": "Undo",
    "btn_delete": "Delete",
    "btn_edit_amount": "Edit amount",
    "btn_edit_note": "Edit note",
    "btn_change_category": "Change category",
    "btn_add_category": "➕ New category",
    "btn_rename": "Rename",
    "btn_cancel": "Cancel",
    "btn_skip": "Skip",
    # generic
    "cancelled": "Cancelled.",
    "error_generic": "Something went wrong. Please try again.",
    "rate_limited": "You are doing that too often. Try again in a moment.",
    "not_found": "I could not find that any more.",
    "uncategorized": "Uncategorized",
    # command menu descriptions (shown by Telegram's Menu button)
    "cmd_add": "Record an expense",
    "cmd_list": "Browse and edit recent expenses",
    "cmd_report": "This month's summary and chart",
    "cmd_categories": "Manage your categories",
    "cmd_export": "Download your expenses as CSV",
    "cmd_remind": "Daily reminder to log spending",
    "cmd_language": "Change language",
    "cmd_settings": "Show current settings",
    "cmd_help": "Show help",
    # built-in category names (keyed by slug)
    "category.food": "Food",
    "category.transport": "Transport",
    "category.housing": "Housing",
    "category.bills": "Bills",
    "category.health": "Health",
    "category.shopping": "Shopping",
    "category.fun": "Entertainment",
    "category.other": "Other",
    # month names
    "month.1": "January",
    "month.2": "February",
    "month.3": "March",
    "month.4": "April",
    "month.5": "May",
    "month.6": "June",
    "month.7": "July",
    "month.8": "August",
    "month.9": "September",
    "month.10": "October",
    "month.11": "November",
    "month.12": "December",
}

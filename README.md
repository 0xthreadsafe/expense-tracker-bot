# expense-tracker-bot

A Telegram bot for tracking personal expenses — quick entry, category keyboards,
monthly reports with charts, and CSV export.

> Work in progress. See the Linear project for the roadmap.

## Stack

- Python 3.11+, [python-telegram-bot](https://python-telegram-bot.org/) 21 (async)
- SQLAlchemy 2 (async) over SQLite, Postgres-ready
- pytest, ruff, mypy
- Docker + GitHub Actions

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # add your BOT_TOKEN from @BotFather
expensebot
```

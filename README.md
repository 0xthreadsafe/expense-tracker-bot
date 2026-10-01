# expense-tracker-bot

A Telegram bot for tracking personal expenses — quick entry, category keyboards,
monthly reports with charts, and CSV export. Available in English and Persian.

> Work in progress.

## Stack

- Python 3.12, [python-telegram-bot](https://python-telegram-bot.org/) 21 (async)
- SQLAlchemy 2 (async) over SQLite, Postgres-ready
- [uv](https://docs.astral.sh/uv/) for dependency and Python version management
- pytest, ruff, mypy
- Docker + GitHub Actions

## Quick start

```bash
uv sync                 # creates .venv and installs the locked dependencies
cp .env.example .env    # add your BOT_TOKEN from @BotFather
uv run expensebot
```

`uv` reads `.python-version` and fetches Python 3.12 if it is not already
installed, so no manual virtualenv step is needed. `uv.lock` is committed, so
every clone resolves to identical dependency versions.

Common tasks:

```bash
uv run ruff check . && uv run ruff format .   # lint and format
uv run mypy                                   # type check
uv run pytest                                 # tests
```

## Configuration

Every setting is read from the environment (or `.env`) and validated at startup;
a missing or malformed value stops the process with a precise message rather
than failing later at runtime. See `.env.example` for the full list.

`BOT_MODE` selects how updates arrive: `polling` for local development (no
public URL required) or `webhook` for deployment.

# expense-tracker-bot

A Telegram bot for tracking personal expenses, in **English and Persian**.
Send it an amount, tap a category, and get a monthly report with a chart.

Built as a demonstration of a production-shaped Python service: typed
configuration, async persistence, a translation layer designed for languages
that do not exist yet, tests, and a container that runs as a non-root user.

```
You  ›  25000 lunch
Bot  ›  25,000 IRR — lunch
        Which category?
        [🍔 Food] [🚌 Transport] [🏠 Housing] …
Bot  ›  ✅ Saved 25,000 IRR under 🍔 Food.           [Undo]
```

## Features

- **Fast entry** — send `25000 lunch`, or `/add 25000 lunch`. Understands
  `25k`, `۲۵ هزار`, `2m`, grouped thousands and both decimal separators.
- **Categories** — eight built-ins, seeded already translated, plus your own.
- **History** — paginated `/list`, with inline editing of amount, note and
  category, and delete.
- **Reports** — `/report` gives a monthly total, a per-category breakdown with
  shares, a comparison against the previous month, and a chart.
- **Export** — `/export` produces a CSV that opens correctly in Excel, Persian
  text intact.
- **Reminders** — opt-in nightly nudge, in your own timezone, only when you
  have logged nothing that day.
- **Two languages** — switch any time with `/language`; new users are matched
  to their Telegram language automatically. The command menu beside the input
  box is published by the bot itself, in both languages.

## Commands

| Command | What it does |
| --- | --- |
| `/start` | Register and seed categories |
| `/add <amount> [note]` | Record an expense (or just send the text) |
| `/list [YYYY-MM]` | Browse and edit recent expenses |
| `/report [last\|YYYY-MM]` | Monthly summary and chart |
| `/categories` | Add, rename, hide or remove categories |
| `/export [YYYY-MM]` | Download expenses as CSV |
| `/remind 21:30` / `/remind off` | Daily reminder |
| `/language`, `/settings`, `/help` | Preferences and help |

## Running it

Get a token from [@BotFather](https://t.me/BotFather) — the Bot API is free and
needs no Telegram Premium.

```bash
uv sync
cp .env.example .env     # put your BOT_TOKEN in it
uv run expensebot
```

`uv` reads `.python-version` and fetches Python 3.12 if needed, so there is no
manual virtualenv step. `uv.lock` is committed, so every clone resolves to
identical versions.

With Docker instead:

```bash
docker compose up --build                      # SQLite on a named volume
docker compose --profile postgres up --build   # Postgres
```

### Development

```bash
uv run ruff check . && uv run ruff format .
uv run mypy
uv run pytest
uv run pytest tests/test_parsing.py -q         # a single file
uv run pytest -k "persian" -q                  # a single case
```

## Configuration

Every value is read from the environment (or `.env`) and validated at startup,
so a missing token or an out-of-range port stops the process with a precise
message instead of failing later in a handler.

| Variable | Default | Purpose |
| --- | --- | --- |
| `BOT_TOKEN` | — | Required. From @BotFather |
| `BOT_MODE` | `polling` | `polling` for local use, `webhook` for deployment |
| `WEBHOOK_URL` | — | Required when `BOT_MODE=webhook` |
| `WEBHOOK_PORT` / `WEBHOOK_LISTEN` | `8080` / `0.0.0.0` | Webhook binding |
| `WEBHOOK_SECRET` | — | Verifies requests really came from Telegram |
| `DATABASE_URL` | SQLite in `./data` | Any async SQLAlchemy URL |
| `TIMEZONE` | `Asia/Tehran` | Month boundaries and reminder times |
| `CURRENCY` | `IRR` | Label shown beside amounts |
| `DEFAULT_LOCALE` | `en` | Used when Telegram's language is unrecognised |
| `LOG_LEVEL` | `INFO` | |

**Polling** asks Telegram for updates and works from a laptop with no public
address. **Webhook** has Telegram push updates to an HTTPS URL, which is more
efficient but needs a hostname and certificate. Handlers are identical either
way. See [`docs/architecture.md`](docs/architecture.md).

## How it is put together

```
__main__.py     startup, configuration errors, exit codes
  app.py        builds the Application, registers handlers, picks transport
  handlers/     one module per feature; the only layer that imports telegram
  i18n/         message id + locale -> localized, formatted text
  repository.py intent-shaped data access
  models.py     SQLAlchemy tables
```

Each layer depends only on the one below it, which is what makes the bot
translatable without rewriting handlers and lets parsing, dates and reports be
tested with no database or network.

Decisions worth calling out:

- **Amounts are `Decimal`, never `float`.** Binary floating point cannot hold
  decimal fractions exactly and the error compounds once a month is summed.
- **Timestamps are stored in UTC; months are computed in the user's zone.**
  A user in Tehran logging at 00:30 on the 1st belongs to the new month, which
  a naive UTC query gets wrong.
- **Date ranges are half-open.** Consecutive months then neither overlap nor
  leave a gap at midnight.
- **Nothing is written until the user picks a category**, so an unanswered
  prompt leaves no partial row.
- **Charts render off the event loop.** matplotlib is CPU-bound and would
  otherwise freeze every other user mid-report.
- **Errors are logged in full and reported blandly**, because exception text
  can contain tokens and query fragments.

### Adding a third language

Adding one means writing a `LocaleProfile` and a catalog — no handler changes.
The profile carries the catalog, writing direction, digit set and separators,
and the `/language` keyboard is generated from the registry. A test registers a
synthetic locale and asserts the bot renders with it, so that guarantee cannot
quietly rot. Catalog and placeholder parity are enforced by tests too.

Another left-to-right language is a translation job. Another right-to-left one
is nearly free, since Persian already pays for the bidirectional handling.

## Known limits

Deliberate, and the reasoning is in `docs/`:

- **Dates are Gregorian in both languages**, and **chart labels are English**.
  Persian chart labels need a text reshaper, a bidi pass and a bundled font;
  built-in categories chart under their English names and unrenderable custom
  names fall back to their slug, so nothing renders as broken glyphs.
- **The schema is created at startup rather than migrated.** Fine for a sample;
  a long-lived deployment would add Alembic.
- **Reports and exports cap at 1000 rows** per call.

## Licence

MIT.

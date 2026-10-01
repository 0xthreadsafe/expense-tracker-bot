# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Dependencies are managed with `uv` against a committed `uv.lock`, and the
Python version is pinned by `.python-version`. There is no manual virtualenv
step.

```bash
uv sync                                 # install; creates .venv
uv run expensebot                       # run the bot (needs BOT_TOKEN in .env)
uv run pytest                           # all tests
uv run pytest tests/test_parsing.py -q  # one file
uv run pytest -k persian -q             # one case by name
uv run ruff check . && uv run ruff format .
uv run mypy                             # checks src and tests
docker build -t expense-tracker-bot .
```

CI runs ruff, `ruff format --check`, mypy and pytest on Python 3.11–3.13, plus
a Docker build. `uv sync --frozen` there means a `pyproject.toml` change
without a regenerated `uv.lock` fails the build; run `uv lock` after editing
dependencies.

## Architecture

Telegram does not host this code: the bot is a process that talks to Telegram's
API, and the token is only an identity. `BOT_MODE` selects polling (outbound
requests, works from a laptop) or webhook (Telegram pushes to a public HTTPS
URL). Handlers are identical in both. Longer explanation in
`docs/architecture.md`.

Layering, where each layer depends only on the one beneath it:

```
__main__.py -> app.py -> handlers/ -> i18n/ -> repository.py -> models.py
```

Three rules this implies, and breaking them is what reviews should catch:

- **Handlers never write SQL.** They call `repository` functions, which are
  named for intent and always scope reads by `user_id`.
- **Handlers never contain user-facing literals.** Every string goes through
  `t(key, locale)`; a new message means a new key in *both* catalogs.
- **`repository.py` and `parsing.py` never import `telegram`.** That is what
  keeps them testable without a network.

`app.py:register_handlers` is the single place handlers are attached. Order
matters: `expenses.register` installs a catch-all text handler and must stay
second to last, with `errors.register` last, or it will shadow the
conversation steps in `categories` and `listing`.

## Localization

`i18n/__init__.py` holds `LocaleProfile` and the `LOCALES` registry; catalogs
live in `i18n/catalogs/`. **Never branch on a locale code in application
code** — anything that varies per language belongs on the profile. Adding a
language should be one profile plus one catalog, and `tests/test_i18n.py`
asserts exactly that with a synthetic locale.

Lookup falls back per key to English, so a partial translation degrades rather
than breaks. Tests enforce catalog key parity and placeholder parity; adding a
key to `en.py` without `fa.py` fails CI.

Numbers adopt the locale's digit set wherever they appear in a rendered
message, and amounts are wrapped in Unicode isolates so digit runs are not
reordered inside Persian text.

## Money and time

- Amounts are `Decimal` end to end and `Numeric` in the database. Do not
  introduce `float`.
- Timestamps are stored timezone-aware in UTC; `periods.py` converts to the
  user's zone to compute month and day boundaries. Ranges are half-open
  (`start <= x < end`), which is why consecutive months neither overlap nor
  gap.
- `parsing.py` accepts Persian, Arabic-Indic and Western digits, both decimal
  separators and multiplier words in either language. It raises `ParseError`
  carrying a **translation key**, never English text, so handlers can render
  the failure in the user's language.

## Deliberate limits

Do not "fix" these without asking; they are decisions, not oversights.

- **Dates are Gregorian and chart labels English in every locale.** matplotlib
  does no Arabic shaping, so Persian labels would render as broken glyphs
  without a reshaper, bidi pass and bundled font. `charts.chart_label` falls
  back from the English built-in name, to a Latin custom name, to the slug.
- **Schema is created at startup**, not migrated. Alembic is out of scope.
- Reports and exports cap at 1000 rows.

## Conventions

- Comments explain *why*, not what. Several non-obvious decisions above are
  documented at their call sites; keep that up.
- Tests assert behaviour and name the bug they prevent.
- CSV export is UTF-8 **with BOM** (Excel) and ISO dates regardless of locale.
- Chart rendering must stay inside `asyncio.to_thread`; it is CPU-bound and
  blocks every other user otherwise.
- Error replies are generic by design — exception text can carry tokens.

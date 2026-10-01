# Architecture

## What a Telegram bot actually is

Telegram does not run your code. A bot is an ordinary program, running on a
machine you control, that talks to Telegram's HTTP API. The token issued by
@BotFather is an identity badge: it proves the program is allowed to act as
that bot. When the program stops, the bot stops answering.

```
┌──────────┐      ┌─────────────────┐      ┌──────────────────┐
│  User's  │◄────►│  Telegram's     │◄────►│  This program    │
│ Telegram │      │  servers        │      │                  │
└──────────┘      └─────────────────┘      └────────┬─────────┘
                                                    │
                                           ┌────────▼─────────┐
                                           │  Database        │
                                           └──────────────────┘
```

The program never contacts a user directly; Telegram relays in both directions.

Telegram stores no application state. It will not remember that a user spent
25,000 on lunch, so anything worth keeping must be written to the database.
That is why the persistence layer is built before any feature.

## Receiving updates: polling vs webhook

Both modes are supported and selected with `BOT_MODE`. Handlers are identical
either way; only the transport differs.

**Polling** — the program repeatedly asks Telegram whether anything new has
arrived. Requests go outward only, so it works from a laptop behind a home
router with no public address. This is the development default.

**Webhook** — Telegram sends an HTTPS POST to a public URL whenever something
happens. Lower latency and far fewer wasted requests, at the cost of needing a
public hostname and a valid TLS certificate.

|                    | Polling            | Webhook          |
| ------------------ | ------------------ | ---------------- |
| Who initiates      | This program       | Telegram         |
| Needs public URL   | No                 | Yes              |
| Runs on a laptop   | Yes                | No               |
| Suited to          | Development        | Production       |

## Request lifecycle

What happens when a user sends `/add 25000 lunch`:

1. Telegram receives the message and hands it to this program, by polling
   response or webhook POST.
2. `python-telegram-bot` parses it into an `Update` object.
3. The dispatcher matches the update against registered handlers.
4. The handler runs: parse the amount, resolve the user's locale, persist the
   expense, build a reply.
5. The reply is an outbound HTTPS call to Telegram, which delivers it.

Steps 1–3 and 5 belong to the library. Application code is step 4.

## Layering

```
__main__.py     startup, configuration errors, exit codes
    │
  app.py        builds the Application, registers handlers, picks transport
    │
handlers/       one module per feature; the only layer aware of Telegram
    │
  i18n/         message id + locale -> localized, correctly formatted text
    │
repository.py   intent-shaped data access ("expenses for this month")
    │
 models.py      SQLAlchemy tables
```

Each layer depends only on the one beneath it. The rules that follow from that:

- Handlers never write SQL. They call the repository.
- Handlers never contain literal user-facing strings. They call `t()`.
- The repository never imports anything from `telegram`.

This is what keeps the bot translatable without rewriting handlers, and what
allows parsing, formatting and reporting logic to be tested without a database
or a network connection.

`config.py` and `logging_setup.py` are cross-cutting and may be imported by any
layer.

## Concurrency

Handlers are `async` because a bot spends nearly all of its time waiting on the
network or the database. While one update waits, the event loop serves others,
so a single process handles many users concurrently.

The hazard is CPU-bound work, which blocks the loop and therefore every other
user. Chart rendering is the one such case here and is pushed to a worker
thread with `asyncio.to_thread`.

## Persistence

SQLAlchemy 2 in async mode, over SQLite by default and Postgres in production;
only `DATABASE_URL` changes between them. Amounts are stored as `Numeric`
rather than float, because binary floating point cannot represent decimal money
exactly and errors accumulate across sums.

Schema is created at startup rather than through migrations. That is a
deliberate simplification for a sample project; a long-lived deployment would
add Alembic so that schema changes do not require recreating the database.

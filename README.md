# NestKeeper

A serverless Telegram bot that manages an e-mail mailing list for a self-administered group.
It runs only on Cloudflare's free tier: a Python Worker, D1, Email Routing, Cron Triggers and R2.

* `/get_mail_list`: replies with the list address.
* `/add_me_to_mail_list`: collects the user's e-mail, privately (deep link) or as a reply in
  the group (the bot deletes that reply), and registers it as a Cloudflare Email Routing
  destination. Cloudflare sends a verification link.
* Mail sent to the list address goes to the Worker's `email` handler, which forwards it to
  every verified subscriber except the sender.
* The bot only works in allow-listed groups and never talks to users outside these flows.
  All user-facing text is Ukrainian (`src/nestkeeper/texts.py`).

## Documentation

1. [Telegram bot](docs/01-telegram-bot.md)
2. [Cloudflare account, tokens, R2](docs/02-cloudflare-account.md)
3. [Infrastructure (OpenTofu)](docs/03-infrastructure.md)
4. [GitHub Actions (secrets, variables, workflows)](docs/04-github-actions.md)
5. [Local development](docs/05-local-development.md)
6. [Backup and restore](docs/06-backup-restore.md)
7. [Operations](docs/07-operations.md)

## Quick start (development)

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest
```

## Known risks (verify on the first deploy)

* **Python Worker `email` handler**: `Default.email()` in `src/nestkeeper/entry.py`. If the
  Python runtime doesn't dispatch email events, move only the fan-out to a small JS Worker
  bound to the same D1 database. The logic is in `emailing.fan_out`.
* **10 ms CPU limit** on the free plan with Python cold starts: check CPU time in the metrics.
* Calling `message.forward()` once per subscriber: check delivery on a list with ≥ 2 subscribers.

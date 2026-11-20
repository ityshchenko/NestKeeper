# 5. Local development

## Requirements

* **Python 3.14**, the newest version Python Workers support (selected by
  `compatibility_date >= 2026-09-08` in `wrangler.toml.tmpl`). It's pinned in
  `.python-version` / `requires-python`. `uv sync` uses a uv-managed CPython 3.14 by default
  (and downloads it if missing). To use the Nix-provided interpreter instead:
  ```sh
  uv venv --python /run/current-system/sw/bin/python3.14 && uv sync
  # or for every uv command: export UV_PYTHON_PREFERENCE=only-system
  ```
* [uv](https://docs.astral.sh/uv/) **≥ 0.13.4** (`pywrangler` refuses older versions; the
  lint/test commands below work with older uv too)
* Node.js ≥ 20 (wrangler runs through `npx`); only needed for `pywrangler dev`/`deploy`
* OpenTofu ≥ 1.8 (for `infra/`)

## Quality gate

```sh
uv sync                      # creates .venv with runtime + dev dependencies
uv run ruff check            # lint
uv run ruff format --check   # formatting (use `uv run ruff format` to fix)
uv run mypy                  # strict type checking (pydantic plugin)
uv run pytest                # tests + coverage (fails under 90 %) + typeguard runtime checks
```

Notes:

* The tests run `migrations/*.sql` against in-memory SQLite (D1 is SQLite), and fake the
  Telegram and Cloudflare HTTP APIs (`tests/fakes.py`).
* `tests/conftest.py` must not import `nestkeeper` at module level. Otherwise typeguard
  can't instrument the package (`tests/test_typeguard.py` guards this).
* Every user-facing string lives in `src/nestkeeper/texts.py` (Ukrainian). Tests check that
  outgoing messages only use those strings.

## Code layout

| Module | Role |
|---|---|
| `entry.py` | Workers runtime adapters only (fetch client, D1, email message, `Default` entrypoint); excluded from coverage |
| `app.py` | Runtime-independent HTTP routing, email and cron handlers |
| `handlers.py` | Telegram update logic |
| `admin.py` | `/admin/setup`, `/admin/export` |
| `emailing.py` | Fan-out + verification sync |
| `storage.py` | `Database` protocol + typed `Repository` |
| `clients/` | Telegram and Cloudflare API clients over an injectable `HttpClient` |
| `src/worker.py` | `main` module referenced from `wrangler.toml` |

## Running the Worker locally

1. Render `wrangler.toml` (git-ignored):
   ```sh
   export WORKER_NAME=nestkeeper D1_DATABASE_ID=00000000-0000-0000-0000-000000000000 \
          BOT_USERNAME=MyTestBot MAIL_LIST=list@example.org \
          ALLOWED_CHAT_IDS=-1001234567890 CLOUDFLARE_ACCOUNT_ID=<id>
   uv run python scripts/render_wrangler.py
   ```
2. Create `.dev.vars` (git-ignored) with the secrets. **Use a separate test bot** so you don't
   touch the production webhook:
   ```ini
   BOT_TOKEN=123:test-token
   WEBHOOK_SECRET=local-webhook-secret-123
   ADMIN_TOKEN=local-admin-token-123456
   CF_API_TOKEN=<token with Email Routing Addresses: Edit>
   ```
3. Create the local D1 schema and start the Worker:
   ```sh
   npx --yes wrangler@4 d1 migrations apply nestkeeper --local
   uv run pywrangler dev           # http://localhost:8787
   ```
4. Send a sample update:
   ```sh
   curl -s localhost:8787/webhook \
     -H 'X-Telegram-Bot-Api-Secret-Token: local-webhook-secret-123' \
     -H 'content-type: application/json' \
     -d '{"update_id":1,"message":{"message_id":10,"date":0,
          "chat":{"id":-1001234567890,"type":"supergroup"},
          "from":{"id":42,"is_bot":false,"first_name":"A","username":"alice"},
          "text":"/add_me_to_mail_list"}}'
   ```
5. Inspect the local database:
   ```sh
   npx --yes wrangler@4 d1 execute nestkeeper --local --command "SELECT * FROM pending"
   ```
6. Trigger the cron handler: `curl "localhost:8787/__scheduled?cron=*/15+*+*+*+*"`
   (with `uv run pywrangler dev --test-scheduled`).

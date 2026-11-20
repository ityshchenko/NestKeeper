# 4. GitHub Actions

## Workflows

| File | Trigger | What it does |
|---|---|---|
| `.github/workflows/ci.yml` | PR, push to `master`, called by deploy | `uv sync --locked` → `ruff check` → `ruff format --check` → `mypy` (strict) → `pytest` (coverage ≥ 90 %, typeguard; uploads `coverage.xml`). `tofu fmt -check` + `validate` for both modules. **On PRs from this repo only:** `tofu plan` of `infra/core` (`-lock=false`). |
| `.github/workflows/deploy.yml` | push to `master`, manual | Runs CI, then in the `production` environment (concurrency group `deploy-production`): `tofu apply infra/core` → render `wrangler.toml` → `wrangler d1 migrations apply --remote` → `pywrangler deploy` → `wrangler secret bulk` → `tofu apply infra/routing` → `POST /admin/setup` (webhook + commands). |

## Setup

1. **Settings → Environments → New environment** → `production`. Optionally add required
   reviewers or restrict it to `master`.
2. Add the secrets and variables below. Put the **infra secrets** (`CLOUDFLARE_API_TOKEN`,
   `R2_*`) at the **repository** level so the PR `tofu plan` job can read them without
   environment approval. Put the bot secrets in the `production` environment.

### Secrets

| Name | Scope | Value |
|---|---|---|
| `CLOUDFLARE_API_TOKEN` | repository | Deploy token ([02 §2.3](02-cloudflare-account.md#23-api-tokens)) |
| `R2_ACCESS_KEY_ID` | repository | R2 key id ([02 §2.4](02-cloudflare-account.md#24-r2-bucket-for-opentofu-state)) |
| `R2_SECRET_ACCESS_KEY` | repository | R2 secret |
| `CF_EMAIL_API_TOKEN` | production | Runtime token (Email Routing Addresses: Edit). Stored in the Worker as `CF_API_TOKEN`. |
| `BOT_TOKEN` | production | From @BotFather |
| `WEBHOOK_SECRET` | production | Random, ≥ 16 chars, only `A-Z a-z 0-9 _ -`: `openssl rand -hex 32` |
| `ADMIN_TOKEN` | production | Random, ≥ 16 chars: `openssl rand -hex 32`. Protects `/admin/*`. |

### Variables

| Name | Example | Notes |
|---|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | `0123abcd…` | |
| `CLOUDFLARE_ZONE_ID` | `4567efgh…` | Zone of the mail-list domain |
| `TF_STATE_BUCKET` | `nestkeeper-tfstate` | R2 bucket |
| `WORKER_NAME` | `nestkeeper` | Also used by the email routing rule |
| `WORKER_URL` | `https://nestkeeper.<sub>.workers.dev` | Webhook base URL |
| `BOT_USERNAME` | `NestKeeperApp` | Without `@` |
| `MAIL_LIST` | `list@example.org` | Must be on `CLOUDFLARE_ZONE_ID` |
| `ALLOWED_CHAT_IDS` | `-1001234567890,-1009876543210` | Comma-separated |
| `RESTRICT_SENDERS` | `false` | `true` = only verified subscribers may post to the list |

## Behaviour notes

* Deploys never overlap (`cancel-in-progress: false`), so a running deploy finishes before the next one starts.
* The D1 database has `prevent_destroy`, so automation can't delete subscriber data.
* Changing any variable or secret only takes effect after the next deploy run
  (**Actions → Deploy → Run workflow**).
* The secrets JSON for `wrangler secret bulk` goes to `$RUNNER_TEMP` and is deleted at the end of the step.

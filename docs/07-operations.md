# 7. Operations

## Logs

The Worker writes one JSON object per log line (structlog). Workers Logs collects these
(`[observability] enabled = true`). E-mail addresses are masked (`a***@example.com`).

* Dashboard → **Workers & Pages** → `nestkeeper` → **Logs**: filter e.g. `event = "register_failed"`.
* Live tail: `npx --yes wrangler@4 tail nestkeeper --format pretty`.

Useful events: `group_not_allowed` (with `chat_id`), `subscriber_registered`, `register_failed`,
`delete_message_failed`, `webhook_forbidden`, `update_failed`, `email_fanned_out`,
`email_rejected`, `forward_failed`, `verification_synced`.

## Adding or removing an allowed group

1. Find the id ([01 §1.4](01-telegram-bot.md#14-find-the-group-chat-id)).
2. Edit the `ALLOWED_CHAT_IDS` GitHub variable (comma-separated).
3. **Actions → Deploy → Run workflow**.

## Rotating secrets

| Secret | Steps |
|---|---|
| `BOT_TOKEN` | @BotFather `/revoke` → update GH secret → run Deploy (re-registers webhook). |
| `WEBHOOK_SECRET` | Update GH secret → run Deploy (`/admin/setup` sends the new secret to Telegram). |
| `ADMIN_TOKEN` | Update GH secret → run Deploy. |
| `CF_EMAIL_API_TOKEN` | Roll the token in Cloudflare → update GH secret → run Deploy. |
| `CLOUDFLARE_API_TOKEN`, `R2_*` | Roll in Cloudflare → update GH secrets. |

## Removing a subscriber

```sh
npx --yes wrangler@4 d1 execute nestkeeper --remote \
  --command "DELETE FROM subscribers WHERE tg_user_id = 123456"
```

Optionally also delete the destination address: dashboard → **Email** → **Email Routing** →
**Destination addresses**.

## Re-running the setup manually

```sh
curl -fsS -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "$WORKER_URL/admin/setup"
curl -s "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo" | jq
```

## Free-tier limits to keep in mind

* Workers: 100k requests/day, **10 ms CPU** per invocation (Python cold starts use memory
  snapshots). Check *CPU time* in the Worker metrics after deploy.
* D1: 5 GB, 5M rows read/day. Email Routing: no fan-out size limit is documented, but every
  `forward()` is one outgoing delivery. Keep the list modest.

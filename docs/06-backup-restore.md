# 6. Backup and restore

Subscriber data lives in two places:

* **D1** (`subscribers`, `members`, `pending`): the source of truth for the bot.
* **Cloudflare Email Routing destination addresses**: account-level, hold the
  verification state. D1 is re-synced from them every 15 minutes.

## Full SQL dump (recommended)

```sh
export CLOUDFLARE_API_TOKEN=<token with D1: Edit>  CLOUDFLARE_ACCOUNT_ID=<id>
npx --yes wrangler@4 d1 export nestkeeper --remote --output "nestkeeper-$(date +%F).sql"
```

The dump contains schema + data (including the `d1_migrations` table). Store it offline and
encrypted. It contains personal data (e-mail addresses, Telegram ids).

## CSV export of subscribers

```sh
curl -fsS -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$WORKER_URL/admin/export" -o "subscribers-$(date +%F).csv"
```

Columns: `tg_user_id, tg_username, email, source_chat_id, verified, cf_address_id, created_at, updated_at`.

## Restore

Into a **new, empty** database (e.g. after accidental data loss):

```sh
npx --yes wrangler@4 d1 create nestkeeper-restore      # or let OpenTofu create it
npx --yes wrangler@4 d1 execute nestkeeper-restore --remote --file nestkeeper-2026-11-20.sql
```

Then point the deployment at it: either import it into OpenTofu state
(see [03](03-infrastructure.md#importing-existing-resources)) or rename. Redeploy, and run the
next cron (or wait 15 min) to refresh `verified` from Cloudflare.

To restore into the **existing** database, delete the rows first. The dump's `CREATE TABLE`
statements would otherwise fail:

```sh
npx --yes wrangler@4 d1 execute nestkeeper --remote \
  --command "DELETE FROM subscribers; DELETE FROM members; DELETE FROM pending;"
grep '^INSERT' nestkeeper-2026-11-20.sql | grep -v d1_migrations > data.sql
npx --yes wrangler@4 d1 execute nestkeeper --remote --file data.sql
```

D1 also has built-in **Time Travel** (point-in-time restore, last 7 days on the free plan):
`npx wrangler d1 time-travel restore nestkeeper --timestamp <ISO-8601>`.

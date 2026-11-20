# 2. Cloudflare account

Everything runs on Cloudflare's **free plan**: Workers (Python), D1, Email Routing, Cron
Triggers, Workers Logs and R2 (OpenTofu state).

## 2.1 Zone

The mail-list address (e.g. `list@example.org`) must be on a domain (zone) in your Cloudflare
account that uses Cloudflare nameservers.

* **Account ID**: dashboard → any zone → *Overview* → right sidebar → *Account ID* → `CLOUDFLARE_ACCOUNT_ID`.
* **Zone ID**: same sidebar → *Zone ID* → `CLOUDFLARE_ZONE_ID`.

## 2.2 Email Routing

OpenTofu (`infra/core`) enables Email Routing on the zone. If the zone already has
other MX records, Cloudflare refuses until you remove them. To do this once by hand instead:
dashboard → zone → **Email** → **Email Routing** → *Get started* → *Add records and enable*.

Subscribers are stored as **destination addresses** (account level). Cloudflare e-mails each one
a verification link, and forwarding only works after the link is clicked. The Worker's cron job
copies the verification state into D1 every 15 minutes.

## 2.3 API tokens

Create both under **My Profile → API Tokens → Create Token → Custom token**.

### `CLOUDFLARE_API_TOKEN` (CI deploy + OpenTofu)

| Type | Resource | Permission |
|---|---|---|
| Account | Workers Scripts | Edit |
| Account | D1 | Edit |
| Account | Account Settings | Read |
| Zone | Email Routing Rules | Edit |
| Zone | Zone Settings | Edit |
| Zone | DNS | Edit |
| Zone | Zone | Read |

*Account Resources*: your account. *Zone Resources*: *Specific zone* → the mail-list domain.

### `CF_EMAIL_API_TOKEN` (used by the Worker at runtime)

| Type | Resource | Permission |
|---|---|---|
| Account | Email Routing Addresses | Edit |

This is the only permission the running bot has. It can create and list destination addresses, nothing else.

## 2.4 R2 bucket for OpenTofu state

1. Dashboard → **R2 Object Storage** → enable R2 (free tier: 10 GB). Cloudflare may ask for a
   payment method, but the bot stays within the free allowance.
2. **Create bucket** → name e.g. `nestkeeper-tfstate` → this is the `TF_STATE_BUCKET` variable.
3. R2 → **Manage R2 API Tokens** → *Create API token* → permission **Object Read & Write**,
   *Apply to specific buckets only* → `nestkeeper-tfstate`.
4. Save the **Access Key ID** → `R2_ACCESS_KEY_ID` and the **Secret Access Key** →
   `R2_SECRET_ACCESS_KEY`. The S3 endpoint is `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`.

## 2.5 workers.dev subdomain

Dashboard → **Workers & Pages** → *Account details* → *Subdomain*. The Worker URL is then
`https://<WORKER_NAME>.<subdomain>.workers.dev` → the `WORKER_URL` variable (used to register the
Telegram webhook).

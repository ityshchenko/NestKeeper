# 3. Infrastructure (OpenTofu)

There are two root modules because the routing rule points at the Worker, and the Worker needs the D1 id first:

| Module | Resources | Applied |
|---|---|---|
| `infra/core` | `cloudflare_d1_database.main` (with `prevent_destroy`), `cloudflare_email_routing_settings.main` | before the Worker deploy |
| `infra/routing` | `cloudflare_email_routing_rule.mail_list`: `MAIL_LIST` → Worker | after the Worker deploy |

`infra/core` outputs `database_id` and `database_name`. CI renders them into `wrangler.toml`.

Provider: `cloudflare/cloudflare ~> 5.0`, pinned by the committed `.terraform.lock.hcl` files.
The provider authenticates with the `CLOUDFLARE_API_TOKEN` environment variable.

## Backend (state in R2)

Both modules use the `s3` backend with R2-specific flags (`region = "auto"`,
`use_path_style`, `skip_*`). The bucket and endpoint are passed at init time:

```sh
export AWS_ACCESS_KEY_ID=<R2_ACCESS_KEY_ID>
export AWS_SECRET_ACCESS_KEY=<R2_SECRET_ACCESS_KEY>
export CLOUDFLARE_API_TOKEN=<deploy token>
ACCOUNT_ID=<CLOUDFLARE_ACCOUNT_ID>

tofu -chdir=infra/core init \
  -backend-config="bucket=nestkeeper-tfstate" \
  -backend-config="endpoints={s3=\"https://${ACCOUNT_ID}.r2.cloudflarestorage.com\"}"
```

State keys: `nestkeeper/core.tfstate` and `nestkeeper/routing.tfstate`.

## Local plan

```sh
export TF_VAR_account_id=$ACCOUNT_ID TF_VAR_zone_id=<CLOUDFLARE_ZONE_ID>
tofu -chdir=infra/core plan

export TF_VAR_mail_list=list@example.org TF_VAR_worker_name=nestkeeper
tofu -chdir=infra/routing init  # same -backend-config flags as above
tofu -chdir=infra/routing plan
```

Offline checks (CI runs these on every push/PR):

```sh
tofu fmt -check -recursive infra
tofu -chdir=infra/core init -backend=false && tofu -chdir=infra/core validate
tofu -chdir=infra/routing init -backend=false && tofu -chdir=infra/routing validate
```

## Importing existing resources

If the D1 database or Email Routing were created by hand, import them before the first apply:

```sh
tofu -chdir=infra/core import cloudflare_d1_database.main "$ACCOUNT_ID/<database_uuid>"
tofu -chdir=infra/core import cloudflare_email_routing_settings.main "<zone_id>"
```

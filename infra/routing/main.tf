# Routes mail sent to the list address into the Worker's email() handler.
# Applied after the Worker exists (Cloudflare validates the worker reference).
resource "cloudflare_email_routing_rule" "mail_list" {
  zone_id = var.zone_id
  name    = "NestKeeper mail list"
  enabled = true

  matchers = [{
    type  = "literal"
    field = "to"
    value = var.mail_list
  }]

  actions = [{
    type  = "worker"
    value = [var.worker_name]
  }]
}

# D1 database holding subscribers, pending prompts and group members.
resource "cloudflare_d1_database" "main" {
  account_id = var.account_id
  name       = var.database_name

  read_replication = {
    mode = "disabled"
  }

  lifecycle {
    # The database holds all subscriber data; never destroy it from automation.
    prevent_destroy = true
  }
}

# Enables Email Routing on the zone (Cloudflare adds the MX/SPF records it needs).
resource "cloudflare_email_routing_settings" "main" {
  zone_id = var.zone_id
}

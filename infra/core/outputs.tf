output "database_id" {
  description = "D1 database UUID, rendered into wrangler.toml."
  value       = cloudflare_d1_database.main.id
}

output "database_name" {
  description = "D1 database name, used by wrangler d1 commands."
  value       = cloudflare_d1_database.main.name
}

variable "account_id" {
  description = "Cloudflare account ID."
  type        = string
}

variable "zone_id" {
  description = "Zone ID of the domain that hosts the mail-list address."
  type        = string
}

variable "database_name" {
  description = "Name of the D1 database."
  type        = string
  default     = "nestkeeper"
}

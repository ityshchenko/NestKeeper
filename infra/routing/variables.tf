variable "zone_id" {
  description = "Zone ID of the domain that hosts the mail-list address."
  type        = string
}

variable "mail_list" {
  description = "Mail-list address, e.g. list@example.org (must be on zone_id)."
  type        = string
}

variable "worker_name" {
  description = "Name of the deployed NestKeeper Worker."
  type        = string
}

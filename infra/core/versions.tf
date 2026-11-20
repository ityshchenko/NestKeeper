terraform {
  required_version = ">= 1.8.0"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.0"
    }
  }

  # State lives in a Cloudflare R2 bucket via the S3-compatible API (free tier).
  # bucket and endpoints are supplied at init time:
  #   tofu init -backend-config="bucket=$BUCKET" \
  #             -backend-config='endpoints={s3="https://<ACCOUNT_ID>.r2.cloudflarestorage.com"}'
  # Credentials: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY = R2 API token key pair.
  backend "s3" {
    key                         = "nestkeeper/core.tfstate"
    region                      = "auto"
    use_path_style              = true
    skip_credentials_validation = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_s3_checksum            = true
  }
}

# Authenticates with the CLOUDFLARE_API_TOKEN environment variable.
provider "cloudflare" {}

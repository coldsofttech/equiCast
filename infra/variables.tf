variable "aws_region" {
  description = "AWS region to deploy equiCast resources into."
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Deployment environment name (e.g. dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name used as a prefix for resource names."
  type        = string
  default     = "equicast"
}

# Not Terraform-managed — Auth0 has no provider config here, the tenant/API
# are created manually (see docs/auth0-setup.md). Shared across dev and prod
# (one tenant, one API), so no per-environment split like
# MARKET_DATA_BUCKET_DEV/PROD. Neither value is sensitive: the domain is a
# public JWKS hostname and the audience is embedded in every issued token's
# `aud` claim, so both are supplied as plain GitHub repo variables, not
# secrets — see terraform.yml.
variable "auth0_domain" {
  description = "Auth0 tenant domain (e.g. equicast.eu.auth0.com), used as the JWT issuer and JWKS host."
  type        = string
}

variable "auth0_audience" {
  description = "Auth0 API Identifier (audience) that access tokens must be issued for."
  type        = string
}

# Product-defined caps for Phase D's S3-JSON domains. Real values come from
# each GitHub Environment's MAX_ACCOUNTS/MAX_PIES/MAX_WATCHLISTS variables
# (see .github/workflows/terraform.yml's apply-dev/apply-prod, which pass
# -var explicitly) so product can retune a cap per environment without a
# code change. The defaults below only matter to `terraform plan`, which
# runs outside any GitHub Environment and so can't see those environment-
# scoped variables — they match equicast_core's own MAX_ACCOUNTS/MAX_PIES/
# MAX_WATCHLISTS code defaults, keeping plan's preview consistent with
# today's behavior.
variable "max_accounts" {
  description = "Max accounts per user (accounts/views.py's AccountLimitExceededError cap)."
  type        = number
  default     = 5
}

variable "max_pies" {
  description = "Max pies per account (pies/views.py's PieLimitExceededError cap)."
  type        = number
  default     = 20
}

variable "max_watchlists" {
  description = "Max watchlists per user (watchlists/views.py's WatchlistLimitExceededError cap)."
  type        = number
  default     = 5
}

variable "max_holdings_for_account" {
  description = "Max holdings directly under one account, not counting pie-scoped ones (HoldingsClient's HoldingLimitExceededError cap)."
  type        = number
  default     = 100
}

variable "max_holdings_for_pie" {
  description = "Max holdings in one pie (HoldingsClient's HoldingLimitExceededError cap)."
  type        = number
  default     = 50
}

variable "max_holdings_for_watchlist" {
  description = "Max holdings in one watchlist (HoldingsClient's HoldingLimitExceededError cap)."
  type        = number
  default     = 20
}

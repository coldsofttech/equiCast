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

# GitHub issue #246: support/views.py's SupportView uses this to create
# issues in the private coldsofttech/equicast-support repo — a
# fine-grained PAT scoped to just `issues:write` on that one repo. Shared
# across dev and prod (one repo, not a per-environment split — see
# ENVIRONMENT_NAME/support/views.py's _ENVIRONMENT_LABELS for how issues
# from each are told apart), so this is a plain repository-level GitHub
# Actions secret, same "no default, no per-environment split" treatment
# terraform.yml gives auth0_domain/auth0_audience — except this one really
# is sensitive, so it's a secret, not a variable. Named without a
# "GITHUB_" prefix because GitHub Actions rejects secrets whose names
# start with that reserved prefix.
variable "support_issue_token" {
  description = "Fine-grained GitHub PAT (issues:write on coldsofttech/equicast-support) for the support form's issue creation."
  type        = string
  sensitive   = true
}

# Repo-level (not per-environment) GitHub Actions variable, same "shared
# across dev and prod" treatment as auth0_domain/auth0_audience above, and
# for the same reason: settings.py's SUPPORT_REPO points both environments
# at the one private equicast-support repo. Not sensitive (it's just a
# repo name), so a plain variable rather than a secret.
variable "support_repo" {
  description = "owner/repo of the private GitHub repo the support form files issues in (settings.py's SUPPORT_REPO)."
  type        = string
}

# GitHub issue #246: environment-scoped, same convention as
# api_rate_limit_per_minute above — a much lower per-minute ceiling than
# the general API budget, applied only to SupportView (see
# support.throttling.SupportRateThrottle). The default here matches
# settings.py's SUPPORT_RATE_LIMIT_PER_MINUTE default so `terraform plan`
# (which can't see GitHub Environment-scoped variables) previews the same
# behavior apply-dev/apply-prod would otherwise get.
variable "support_rate_limit_per_minute" {
  description = "Per-user requests/minute against the support form endpoint (support.throttling.SupportRateThrottle's DEFAULT_THROTTLE_RATES)."
  type        = number
  default     = 2
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

variable "max_goals" {
  description = "Max goals per user (goals/views.py's GoalLimitExceededError cap)."
  type        = number
  default     = 10
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

variable "max_transactions_for_holding" {
  description = "Max transactions recorded against one holding (TransactionsClient's TransactionLimitExceededError cap)."
  type        = number
  default     = 500
}

variable "api_rate_limit_per_minute" {
  description = "Per-user requests/minute across every DRF endpoint (identity.throttling.Auth0UserRateThrottle's DEFAULT_THROTTLE_RATES)."
  type        = number
  default     = 120
}

variable "market_data_cache_ttl_seconds" {
  description = "TTL (seconds) for MarketDataClient's in-process S3 parquet cache — every asset class's ingestion pipeline refreshes at most once a day, so several hours is safe."
  type        = number
  default     = 21600 # 6 hours
}

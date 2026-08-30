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

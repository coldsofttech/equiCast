variable "role_name" {
  description = "Name of the IAM role GitHub Actions assumes via OIDC."
  type        = string
}

variable "github_org" {
  description = "GitHub organization or user that owns the repository allowed to assume this role."
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name allowed to assume this role."
  type        = string
}

variable "bucket_arn" {
  description = "ARN of the S3 bucket this role is granted ingestion access to."
  type        = string
}

variable "s3_prefixes" {
  description = "Key prefixes (without a trailing /*) this role may read/write objects under."
  type        = list(string)
  default     = ["fx=*"]
}

variable "create_oidc_provider" {
  description = "Whether to create the GitHub Actions OIDC provider. Set to false if one already exists in this AWS account (only one is allowed per URL)."
  type        = bool
  default     = true
}

variable "oidc_provider_arn" {
  description = "ARN of an existing GitHub OIDC provider. Required when create_oidc_provider is false."
  type        = string
  default     = ""
}

variable "aws_region" {
  description = "AWS region to deploy equiCast resources into."
  type        = string
  default     = "us-east-1"
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

variable "github_org" {
  description = "GitHub organization or user that owns the repository."
  type        = string
  default     = "coldsofttech"
}

variable "github_repo" {
  description = "GitHub repository name, used to scope the GitHub Actions OIDC trust policy."
  type        = string
  default     = "equiCast"
}

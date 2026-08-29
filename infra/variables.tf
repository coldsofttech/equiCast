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

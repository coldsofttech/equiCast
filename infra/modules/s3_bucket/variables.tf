variable "bucket_name" {
  description = "Name of the S3 bucket."
  type        = string
}

variable "versioning" {
  description = "Whether to enable object versioning."
  type        = bool
  default     = false
}

variable "static_site" {
  description = "Whether to configure the bucket for static website hosting."
  type        = bool
  default     = false
}

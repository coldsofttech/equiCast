variable "bucket_name" {
  description = "Name of the S3 bucket."
  type        = string
}

variable "force_destroy" {
  description = "Allow Terraform to delete this bucket even if it still has objects/versions. Defaults false so a normal apply can never silently lose data; the infra-lifecycle destroy workflow overrides it per-run."
  type        = bool
  default     = false
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

variable "noncurrent_version_expiration_days" {
  description = "If set (requires versioning = true), expire noncurrent object versions after this many days. Bounds storage growth for buckets that accumulate versioned uploads (e.g. deploy artifacts)."
  type        = number
  default     = null
}

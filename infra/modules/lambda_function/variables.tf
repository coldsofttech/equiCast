variable "function_name" {
  description = "Name of the Lambda function (and its IAM role, log group)."
  type        = string
}

variable "handler" {
  description = "Lambda handler, e.g. \"equicast_api.lambda_handler.handler\"."
  type        = string
}

variable "environment_variables" {
  description = "Environment variables exposed to the function."
  type        = map(string)
  default     = {}
}

variable "policy_json" {
  description = "Additional IAM policy document (JSON) to attach to the execution role, beyond basic CloudWatch Logs access. Ignored unless attach_policy is true."
  type        = string
  default     = null
}

# Deliberately separate from policy_json's content: the caller always knows
# statically whether it wants a policy attached, but policy_json's *value*
# can be unknown at plan time (e.g. built from a data source that reads
# other not-yet-created resources' ARNs). Gating `count` on that content
# directly, as `var.policy_json != null`, makes the count itself unknown on
# a from-scratch plan and Terraform refuses with "Invalid count argument" —
# gating on this always-known boolean instead avoids that.
variable "attach_policy" {
  description = "Whether to attach policy_json to the execution role."
  type        = bool
  default     = false
}

variable "memory_size" {
  description = "Memory allocated to the function, in MB."
  type        = number
  default     = 512
}

variable "timeout" {
  description = "Function timeout, in seconds."
  type        = number
  default     = 30
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention for this function's log group."
  type        = number
  default     = 30
}

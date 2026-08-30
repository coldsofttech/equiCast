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
  description = "Additional IAM policy document (JSON) to attach to the execution role, beyond basic CloudWatch Logs access. Null to attach nothing extra."
  type        = string
  default     = null
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

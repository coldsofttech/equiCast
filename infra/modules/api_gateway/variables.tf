variable "api_name" {
  description = "Name of the HTTP API."
  type        = string
}

variable "lambda_invoke_arn" {
  description = "Invoke ARN of the Lambda function to proxy all requests to."
  type        = string
}

variable "lambda_function_name" {
  description = "Name of the Lambda function (for the resource-based invoke permission)."
  type        = string
}

variable "throttling_rate_limit" {
  description = "Sustained requests/second allowed across the whole API (all clients combined) before API Gateway starts rejecting with 429, never reaching Lambda. A blunt, aggregate ceiling — HTTP APIs have no usage-plan/API-key concept for per-client limits, unlike REST APIs (see api_gateway module's own comment on the stage resource)."
  type        = number
  default     = 25
}

variable "throttling_burst_limit" {
  description = "Token-bucket burst capacity above throttling_rate_limit — how many requests can land in a short spike before throttling kicks in."
  type        = number
  default     = 50
}

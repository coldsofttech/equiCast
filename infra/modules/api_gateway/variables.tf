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

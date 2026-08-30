# Placeholder deployment package, used only to give `aws_lambda_function` a
# valid `filename`/`source_code_hash` at creation time. Real code is deployed
# afterwards via `aws lambda update-function-code` (see deploy.yml) — the
# `lifecycle.ignore_changes` block below stops a later `terraform apply` from
# ever reverting the function back to this placeholder.
data "archive_file" "placeholder" {
  type        = "zip"
  source_file = "${path.module}/placeholder/handler.py"
  output_path = "${path.module}/placeholder.zip"
}

resource "aws_iam_role" "this" {
  name = "${var.function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "basic_execution" {
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "additional" {
  count = var.attach_policy ? 1 : 0

  name   = "${var.function_name}-permissions"
  role   = aws_iam_role.this.id
  policy = var.policy_json
}

# Created explicitly (rather than left to Lambda's own auto-create-on-first-
# invocation behavior) so retention is actually bounded — an auto-created log
# group defaults to never expiring. depends_on below ensures this exists
# before the function does, so nothing races to create it first.
resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "this" {
  function_name = var.function_name
  role          = aws_iam_role.this.arn
  handler       = var.handler
  runtime       = "python3.13"
  memory_size   = var.memory_size
  timeout       = var.timeout

  filename         = data.archive_file.placeholder.output_path
  source_code_hash = data.archive_file.placeholder.output_base64sha256

  environment {
    variables = var.environment_variables
  }

  depends_on = [aws_cloudwatch_log_group.this]

  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
}

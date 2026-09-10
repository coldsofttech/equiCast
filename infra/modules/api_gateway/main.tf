# HTTP API (payload format 2.0), one catch-all integration/route — Django's
# own URLconf handles real path routing, API Gateway just needs to forward
# everything to the Lambda function.
resource "aws_apigatewayv2_api" "this" {
  name          = var.api_name
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "this" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.lambda_invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.this.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true

  # A single, aggregate ceiling across every caller combined — HTTP APIs
  # (unlike REST APIs) have no usage-plan/API-key mechanism to throttle
  # per client, and this one catch-all $default route can't distinguish
  # /api/accounts/ from /api/transactions/ either, so this is deliberately
  # coarse: a safety net against a volumetric flood/cost blowout, not
  # per-user fairness (see identity.throttling.Auth0UserRateThrottle in
  # the Django app for that). A request rejected here never reaches
  # Lambda at all, so this can only ever reduce cost under load, never add
  # to it.
  default_route_settings {
    throttling_rate_limit  = var.throttling_rate_limit
    throttling_burst_limit = var.throttling_burst_limit
  }
}

resource "aws_lambda_permission" "apigateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

output "market_data_bucket_name" {
  value = module.market_data_bucket.bucket_name
}

output "backend_lambda_function_name" {
  value = module.backend_lambda.function_name
}

output "backend_api_invoke_url" {
  value = module.backend_api_gateway.invoke_url
}

output "user_profiles_table_name" {
  value = module.user_profiles_table.table_name
}

output "user_data_bucket_name" {
  value = module.user_data_bucket.bucket_name
}

output "frontend_bucket_name" {
  value = module.frontend_bucket.bucket_name
}

# No custom domain yet (see docs/local-setup.md) — this *.cloudfront.net
# hostname is the real, currently-only frontend URL. `terraform output
# frontend_url` after apply to find it.
output "frontend_url" {
  value = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "frontend_cloudfront_distribution_id" {
  description = "Set as the CLOUDFRONT_DISTRIBUTION_ID variable on the development/production GitHub Environments — deploy.yml's frontend jobs need it to invalidate the cache after each deploy."
  value       = aws_cloudfront_distribution.frontend.id
}

output "market_data_bucket_name" {
  value = module.market_data_bucket.bucket_name
}

output "backend_lambda_function_name" {
  value = module.backend_lambda.function_name
}

# The bare API Gateway invoke URL has no /api of its own — Django's
# urls.py roots every real endpoint under api/ (see backend/equicast_api/
# urls.py), the same way frontend/vite.config.js's dev proxy only forwards
# the /api prefix. This output is only ever pasted into the API_URL
# GitHub Environment variable (see docs/terraform-state-setup.md's Step
# 4), so the /api suffix is baked on here rather than left as a manual
# step to remember — the bare invoke URL by itself 404s on every real
# endpoint if used as-is.
output "backend_api_invoke_url" {
  value = "${module.backend_api_gateway.invoke_url}/api"
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

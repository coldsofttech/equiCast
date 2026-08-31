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

# Commented out along with the module in main.tf.
#
# output "frontend_bucket_name" {
#   value = module.frontend_bucket.bucket_name
# }

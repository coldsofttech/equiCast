output "market_data_bucket_name" {
  value = module.market_data_bucket.bucket_name
}

# Commented out along with the modules in main.tf.
#
# output "frontend_bucket_name" {
#   value = module.frontend_bucket.bucket_name
# }
#
# output "backend_ecr_repository_url" {
#   value = module.backend_ecr.repository_url
# }

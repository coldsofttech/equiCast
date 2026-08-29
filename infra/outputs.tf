output "market_data_bucket_name" {
  value = module.market_data_bucket.bucket_name
}

output "frontend_bucket_name" {
  value = module.frontend_bucket.bucket_name
}

output "backend_ecr_repository_url" {
  value = module.backend_ecr.repository_url
}

output "fx_ingestion_role_arn" {
  description = "IAM role ARN GitHub Actions assumes to upload FX Parquet files to S3. Set this as the AWS_FX_INGESTION_ROLE_ARN repo secret."
  value       = module.fx_ingestion_role.role_arn
}

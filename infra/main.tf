module "market_data_bucket" {
  source = "./modules/s3_bucket"

  bucket_name = "${var.project_name}-market-data-${var.environment}"
}

# Frontend/backend aren't ready to deploy yet — commented out to avoid
# paying for the S3 bucket/ECR repo (and their stored objects/images) until
# there's something worth deploying. Uncomment when that changes.
#
# module "frontend_bucket" {
#   source = "./modules/s3_bucket"
#
#   bucket_name = "${var.project_name}-frontend-${var.environment}"
#   static_site = true
# }
#
# module "backend_ecr" {
#   source = "./modules/ecr"
#
#   repository_name = "${var.project_name}-backend"
# }

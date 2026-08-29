module "market_data_bucket" {
  source = "./modules/s3_bucket"

  bucket_name = "${var.project_name}-market-data-${var.environment}"
  versioning  = true
}

module "frontend_bucket" {
  source = "./modules/s3_bucket"

  bucket_name = "${var.project_name}-frontend-${var.environment}"
  static_site = true
}

module "backend_ecr" {
  source = "./modules/ecr"

  repository_name = "${var.project_name}-backend"
}

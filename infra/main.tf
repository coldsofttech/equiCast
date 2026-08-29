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

module "fx_ingestion_role" {
  source = "./modules/github_oidc_role"

  role_name   = "${var.project_name}-fx-ingestion"
  github_org  = var.github_org
  github_repo = var.github_repo
  bucket_arn  = module.market_data_bucket.bucket_arn
  s3_prefixes = ["fx=*"]
}

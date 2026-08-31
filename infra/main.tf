module "market_data_bucket" {
  source = "./modules/s3_bucket"

  bucket_name = "${var.project_name}-market-data-${var.environment}"
}

# Frontend isn't ready to deploy yet — commented out to avoid paying for the
# S3 bucket (and its stored objects) until there's something worth deploying.
# Uncomment when that changes.
#
# module "frontend_bucket" {
#   source = "./modules/s3_bucket"
#
#   bucket_name = "${var.project_name}-frontend-${var.environment}"
#   static_site = true
# }

# Stages the backend's zip deployment package for Lambda to read from —
# needed either way since the real zip is well over the 50MB direct-upload
# limit. Versioned so deploy.yml can promote one exact object version from
# dev to prod (copy-object) rather than rebuilding.
module "backend_deploy_bucket" {
  source = "./modules/s3_bucket"

  bucket_name = "${var.project_name}-backend-deploy-${var.environment}"
  versioning  = true
}

# Minimal user-profile store (see docs/ discussion: DynamoDB holds only the
# small, identity-keyed record; everything else — accounts, portfolios,
# watchlists, holdings — lives as JSON in S3). No sort key, no GSI: every
# access pattern so far is a point lookup by the user's own ID.
module "user_profiles_table" {
  source = "./modules/dynamodb_table"

  table_name = "${var.project_name}-user-profiles-${var.environment}"
  hash_key   = "user_id"
}

# Everything else in Phase D (accounts, and later portfolios/watchlists/
# holdings) — one bucket, domain-prefixed keys (accounts/<user_id>.json,
# ...), rather than a bucket per domain. Kept separate from
# market_data_bucket, which is a read-only ingestion-pipeline artifact store
# (the Lambda only holds s3:GetObject on it) — mixing in writable
# user-owned data would broaden that bucket's IAM footprint and blur two
# unrelated lifecycles.
module "user_data_bucket" {
  source = "./modules/s3_bucket"

  bucket_name = "${var.project_name}-user-data-${var.environment}"
}

# Generated rather than left at the code's insecure hardcoded dev default —
# stored in Terraform state (already S3-backed, encrypted, access-controlled
# via the same OIDC role as everything else here), not a full secrets
# manager, but a real improvement over shipping a literal known string.
resource "random_password" "django_secret_key" {
  length  = 50
  special = false
}

data "aws_iam_policy_document" "backend_lambda_permissions" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${module.market_data_bucket.bucket_arn}/*"]
  }

  statement {
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"]
    resources = [module.user_profiles_table.table_arn]
  }

  # Scoped to accounts/* rather than the whole bucket, so each Phase D
  # domain (portfolios, watchlists, ...) gets its own statement — and its
  # own review — as it's added, instead of one blanket grant covering
  # domains that don't exist yet.
  statement {
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${module.user_data_bucket.bucket_arn}/accounts/*"]
  }
}

module "backend_lambda" {
  source = "./modules/lambda_function"

  function_name = "${var.project_name}-backend-${var.environment}"
  handler       = "equicast_api.lambda_handler.handler"
  attach_policy = true
  policy_json   = data.aws_iam_policy_document.backend_lambda_permissions.json

  environment_variables = {
    MARKET_DATA_BUCKET  = module.market_data_bucket.bucket_name
    DJANGO_SECRET_KEY   = random_password.django_secret_key.result
    USER_PROFILES_TABLE = module.user_profiles_table.table_name
    USER_DATA_BUCKET    = module.user_data_bucket.bucket_name
    AUTH0_DOMAIN        = var.auth0_domain
    AUTH0_AUDIENCE      = var.auth0_audience
  }
}

module "backend_api_gateway" {
  source = "./modules/api_gateway"

  api_name             = "${var.project_name}-backend-${var.environment}"
  lambda_invoke_arn    = module.backend_lambda.invoke_arn
  lambda_function_name = module.backend_lambda.function_name
}

module "market_data_bucket" {
  source = "./modules/s3_bucket"

  bucket_name = "${var.project_name}-market-data-${var.environment}"
}

# React static site bundle. NOT static_site=true (S3 website hosting) —
# that requires the bucket to be public over plain HTTP with no CDN/TLS in
# front of it. Instead this stays fully private (default
# block_public_access) and is only ever read by CloudFront below, via
# Origin Access Control — see the bucket policy after the distribution.
# SPA client-side routing is handled by CloudFront's custom_error_response
# blocks (unknown paths -> /index.html), not S3's error_document, since a
# private REST-endpoint origin doesn't have one.
module "frontend_bucket" {
  source = "./modules/s3_bucket"

  bucket_name = "${var.project_name}-frontend-${var.environment}"
}

# Lets CloudFront (and only CloudFront, via the bucket policy's
# AWS:SourceArn condition below) read the private frontend bucket — the
# standard OAC pattern, replacing the older "Origin Access Identity" one.
resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${var.project_name}-frontend-${var.environment}"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# No custom domain for now (see docs/local-setup.md) — no `aliases`, and
# `viewer_certificate` uses CloudFront's own shared *.cloudfront.net
# certificate rather than an ACM one. Revisit both together once a domain
# is registered.
resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  default_root_object = "index.html"
  comment             = "${var.project_name} frontend (${var.environment})"

  # US/Canada/Europe edge locations only — the cheapest class. Widen to
  # PriceClass_All if/when users outside those regions matter enough to be
  # worth the extra edge-location cost.
  price_class = "PriceClass_100"

  origin {
    domain_name              = module.frontend_bucket.bucket_regional_domain_name
    origin_id                = "frontend-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "frontend-s3"
    viewer_protocol_policy = "redirect-to-https"

    # AWS managed "CachingOptimized" policy — a static SPA bundle needs no
    # custom cache-key/TTL behavior, so no reason to hand-roll one.
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }

  # A React Router client-side route (e.g. /accounts/123) has no matching
  # S3 key, so S3 (via OAC) returns 403 for it — CloudFront rewrites that
  # (and a real 404) to index.html with a 200, and the SPA's own router
  # takes it from there.
  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = module.frontend_bucket.bucket_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudFrontServicePrincipal"
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = "s3:GetObject"
        Resource  = "${module.frontend_bucket.bucket_arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.frontend.arn
          }
        }
      }
    ]
  })
}

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

  # Pies domain (see PiesClient) — same rationale as the accounts statement
  # above: its own statement/review, scoped to pies/* only.
  statement {
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${module.user_data_bucket.bucket_arn}/pies/*"]
  }

  # Watchlists domain (see WatchlistsClient) — same rationale as the
  # accounts/pies statements above: its own statement/review, scoped to
  # watchlists/* only.
  statement {
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${module.user_data_bucket.bucket_arn}/watchlists/*"]
  }

  # Holdings domain (see HoldingsClient) — same rationale as the
  # accounts/pies/watchlists statements above: its own statement/review,
  # scoped to holdings/* only.
  statement {
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${module.user_data_bucket.bucket_arn}/holdings/*"]
  }

  # Transactions domain (see TransactionsClient) — same rationale as the
  # accounts/pies/watchlists/holdings statements above: its own
  # statement/review, scoped to transactions/* only. Also needs
  # s3:DeleteObject, unlike the other domains here — TransactionsClient is
  # partitioned one JSON object per holding rather than per user (see its
  # module docstring), so removing a holding's transactions outright
  # deletes that one object instead of rewriting the user's single object
  # to an empty list the way delete_holdings_for_account/_pies/_watchlist
  # do.
  statement {
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${module.user_data_bucket.bucket_arn}/transactions/*"]
  }

  # s3:ListBucket (a bucket-level action, hence the bucket ARN itself, not
  # .../accounts/*, .../pies/*, .../watchlists/*, .../holdings/*, or
  # .../transactions/*) is required alongside s3:GetObject for a key that
  # might not exist yet: without it, S3 can't tell this role apart from a
  # caller with no rights to know whether the object exists at all, so a
  # GetObject on a not-yet-created accounts/<user_id>.json (or
  # pies/<user_id>.json, watchlists/<user_id>.json, holdings/<user_id>.json,
  # transactions/<user_id>.json) returns AccessDenied instead of the
  # NoSuchKey AccountsClient/PiesClient/WatchlistsClient/HoldingsClient/
  # TransactionsClient._load() catch to mean "nothing yet" — see
  # https://repost.aws/knowledge-center/s3-403-error-list-permissions. The
  # s3:prefix condition keeps this scoped to just the domains that need it
  # — one shared ListBucket statement covering every prefix rather than one
  # per domain, since it's a single bucket-level action with no per-object
  # resource to scope by statement the way GetObject/PutObject are above.
  statement {
    actions   = ["s3:ListBucket"]
    resources = [module.user_data_bucket.bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["accounts/*", "pies/*", "watchlists/*", "holdings/*", "transactions/*"]
    }
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
    # Lambda env vars are always strings; settings.py int()-parses these.
    MAX_ACCOUNTS                 = tostring(var.max_accounts)
    MAX_PIES                     = tostring(var.max_pies)
    MAX_WATCHLISTS               = tostring(var.max_watchlists)
    MAX_HOLDINGS_FOR_ACCOUNT     = tostring(var.max_holdings_for_account)
    MAX_HOLDINGS_FOR_PIE         = tostring(var.max_holdings_for_pie)
    MAX_HOLDINGS_FOR_WATCHLIST   = tostring(var.max_holdings_for_watchlist)
    MAX_TRANSACTIONS_FOR_HOLDING = tostring(var.max_transactions_for_holding)
    # Previously unset here, silently falling back to settings.py's
    # DEBUG default of "true" for every deployed environment (dev and
    # prod alike) — a real information-disclosure risk in prod, since an
    # unhandled exception renders Django's full debug traceback page back
    # to the caller instead of a generic 500. Explicit per-environment now:
    # verbose locally/in dev, off in prod.
    DJANGO_DEBUG = var.environment == "prod" ? "false" : "true"
  }
}

module "backend_api_gateway" {
  source = "./modules/api_gateway"

  api_name             = "${var.project_name}-backend-${var.environment}"
  lambda_invoke_arn    = module.backend_lambda.invoke_arn
  lambda_function_name = module.backend_lambda.function_name
}

# Terraform state setup

`infra/backend.tf` was checked in with its S3 backend commented out, so every
`terraform apply` run in CI used Terraform's default **local** backend — a
state file written to the ephemeral GitHub Actions runner and discarded when
the job finished. Terraform had no memory between runs: the
`equicast-market-data-dev`, `equicast-frontend-dev`, and `equicast-backend`
resources exist in AWS, but no state file knows about them. The next
`terraform apply` would have tried to create them again and failed with
`BucketAlreadyExists`/`RepositoryAlreadyExistsException`.

This is now fixed by enabling a real S3 backend, but that requires a
one-time manual bootstrap (same reasoning as
[aws-github-oidc-setup.md](aws-github-oidc-setup.md): Terraform can't create
the bucket that holds its own state — circular) and importing the
already-existing dev resources into it.

## Step 1: Create the state bucket (once, manually)

```bash
aws s3api create-bucket \
  --bucket equicast-tf-state \
  --region eu-west-1 \
  --create-bucket-configuration LocationConstraint=eu-west-1

aws s3api put-bucket-versioning \
  --bucket equicast-tf-state \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket equicast-tf-state \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

aws s3api put-public-access-block \
  --bucket equicast-tf-state \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

No DynamoDB lock table is needed — `backend.tf` uses `use_lockfile = true`,
Terraform's native S3 state locking (requires Terraform >= 1.10, see
`infra/providers.tf`), which stores the lock alongside the state object in
the same bucket.

No IAM policy changes are needed either: `equicast-tf-state` matches
the `equicast-*` resource pattern the GitHub Actions role's `s3:*` grant
already covers (see `docs/aws-github-oidc-setup.md`), so `terraform init` /
`plan` / `apply` in CI can read and write state without any extra
permissions.

State is split by environment via `-backend-config="key=..."` passed at
`terraform init` time (see `terraform.yml`'s `apply-dev`/`apply-prod` jobs) —
`equicast/dev/terraform.tfstate` and `equicast/prod/terraform.tfstate` in the
same bucket. A backend block's `key` can't be interpolated with
`var.environment`, which is why this is passed on the CLI rather than set in
`backend.tf` directly.

## Step 2: Import the existing dev resources

These were created by earlier `terraform apply` runs before the backend was
enabled — they exist in AWS but aren't in any state file yet. Run this once,
locally, with AWS credentials that can assume (or equivalent to) the
`equicast-github-actions` role:

```bash
cd infra
terraform init -backend-config="key=equicast/dev/terraform.tfstate"

terraform import -var environment=dev \
  module.market_data_bucket.aws_s3_bucket.this equicast-market-data-dev
terraform import -var environment=dev \
  module.market_data_bucket.aws_s3_bucket_versioning.this[0] equicast-market-data-dev
terraform import -var environment=dev \
  module.market_data_bucket.aws_s3_bucket_public_access_block.this equicast-market-data-dev

terraform import -var environment=dev \
  module.frontend_bucket.aws_s3_bucket.this equicast-frontend-dev
terraform import -var environment=dev \
  module.frontend_bucket.aws_s3_bucket_website_configuration.this[0] equicast-frontend-dev
terraform import -var environment=dev \
  module.frontend_bucket.aws_s3_bucket_public_access_block.this equicast-frontend-dev

terraform import module.backend_ecr.aws_ecr_repository.this equicast-backend

terraform plan -var environment=dev
```

That final `plan` should come back with **no changes**. If it wants to
change something (e.g. `image_tag_mutability`, versioning status), that's
real drift between what was manually/previously created and what
`infra/*.tf` now declares — review it before applying.

There's nothing to import for prod: `equicast-market-data-prod` and
`equicast-frontend-prod` don't exist yet. `apply-prod` in `terraform.yml`
(gated behind the `production` GitHub Environment's required reviewers)
creates them fresh the first time it runs.

## Step 3: Configure the GitHub Environments

Three GitHub Environments are in play, across both workflows:

- **`development`** (`terraform.yml` only) — no protection rules; `apply-dev`
  runs automatically on push to `main`. Infra changes are reviewed via the
  Infracost PR comment (see below) before merge, not via an approval gate.
- **`deploy-dev`** (`deploy.yml` only) — add **required reviewers**
  (Settings → Environments → `deploy-dev` → *Required reviewers*) naming the
  admin(s) who approve dev deploys. Kept separate from plain `dev` on
  purpose: gating `dev` itself would also block `terraform.yml`'s
  `apply-dev`, which isn't gated.
- **`production`** (both workflows) — add required reviewers the same way.
  Shared by `apply-prod`, `deploy-backend-prod`, and `deploy-frontend-prod`,
  since all three are "promote to prod" actions gated behind the same
  approval.

Any job wired to an environment with required reviewers pauses in the
Actions UI until one of them approves it. This is enforced by GitHub itself,
independent of what the workflow YAML says.

## Cost estimation (Infracost)

`terraform.yml` runs an `infracost` job on every PR that touches `infra/**`,
posting/updating one PR comment with the estimated monthly cost delta for
both the `dev` and `prod` projects declared in `infracost.yml` (repo root).
It's a pure HCL-based diff — no `terraform plan`, state, or AWS credentials
involved. `infra/infracost-usage.yml` supplies rough usage estimates (S3
storage/requests, ECR storage) since Infracost assumes zero usage by default
for those; tune the numbers there as real usage becomes known, or run
`infracost breakdown --config-file=infracost.yml --sync-usage-file` locally
to regenerate the file with your installed CLI's exact supported keys.

This needs an `INFRACOST_API_KEY` repository secret. Note: Org Settings →
**Service Accounts** in the Infracost Cloud dashboard is for the Cloud API
only ("cannot be used by the CLI or CI/CD") — don't use it for this.

1. Install the Infracost CLI if you don't have it (`brew install infracost`,
   or `curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh`).
2. `infracost auth login` — opens a browser page, logs into your existing
   account, and saves a personal API key locally.
3. `infracost configure get api_key` — prints that key (`ico-...`).
4. Add it as a repo secret: Settings → Secrets and variables → Actions →
   *New repository secret* → name `INFRACOST_API_KEY`, paste the key. (Or via
   CLI: `gh secret set INFRACOST_API_KEY --body "<key>"`.)

`deploy.yml` separately estimates the cost of what's actually being
uploaded that run — `estimate-backend`/`estimate-frontend` build the image
and the frontend bundle once, print a rough cost estimate (published AWS
unit prices, hardcoded and approximate — not looked up live) to the job's
step summary, and hand that same build to the `deploy-dev`/`production`
gated jobs. Reviewers can see the estimate in the run's summary before
approving either gate. `equicast-backend`'s lifecycle policy caps it at the
2 most recently pushed images, so the ECR storage estimate stays roughly
bounded rather than growing forever.

# AWS ↔ GitHub OIDC setup

How GitHub Actions authenticates to AWS — for `terraform.yml` (managing
infrastructure), `deploy.yml` (backend image to ECR, frontend to S3), and
`fx-ingestion.yml`/`stock-ingestion.yml`/`etf-ingestion.yml` (FX/stock/ETF
Parquet files to S3, same bucket). This is the detailed reference;
[fx-pipeline.md](fx-pipeline.md) has the quick-start version.

## Why this is created manually, not by Terraform

`terraform.yml` needs *some* AWS credential to run `terraform plan`/`apply`
in the first place. Having Terraform create the very OIDC provider and role
meant to eliminate long-lived credentials is circular — you'd still need a
static `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` to bootstrap it, which is
exactly what OIDC is meant to replace.

Instead, the OIDC provider and IAM role are created once, manually, outside
of Terraform's management. Every AWS-touching workflow — including
`terraform.yml` itself — then authenticates through that one role. Terraform
never manages its own trust root.

## One role, one secret

There's a single IAM role, trusted via OIDC, used identically by all five
workflows:

```yaml
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
    aws-region: ${{ vars.AWS_REGION || 'eu-west-1' }}
```

- Repo secret **`AWS_ROLE_ARN`** = the role's ARN (see below)
- Repo variable **`AWS_REGION`** (optional, defaults to `eu-west-1`)
- Every job that uses this needs `permissions: id-token: write` — without
  it, GitHub won't issue an OIDC token to the job and this step fails
  immediately.

## Step 1: Create the OIDC identity provider

**Skip this if your AWS account already has one** — an account can only
have one OIDC provider per URL, and this one is commonly shared across
projects. Check first:

```bash
aws iam list-open-id-connect-providers
```

If none exists for `token.actions.githubusercontent.com`:

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

## Step 2: Create the IAM role

Trust policy (`trust-policy.json`) — only this repo, any branch/tag/environment,
can assume it:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<AWS_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:coldsofttech/equiCast:*"
        }
      }
    }
  ]
}
```

```bash
aws iam create-role \
  --role-name equicast-github-actions \
  --assume-role-policy-document file://trust-policy.json
```

## Step 3: Attach the permissions policy

`permissions-policy.json` — scoped to exactly the resource types and naming
convention (`equicast-*`) this project's Terraform and workflows touch,
rather than broad account-wide access:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3BucketManagement",
      "Effect": "Allow",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::equicast-*",
        "arn:aws:s3:::equicast-*/*"
      ]
    },
    {
      "Sid": "EcrRepositoryManagement",
      "Effect": "Allow",
      "Action": "ecr:*",
      "Resource": "arn:aws:ecr:*:<AWS_ACCOUNT_ID>:repository/equicast-*"
    },
    {
      "Sid": "EcrAuth",
      "Effect": "Allow",
      "Action": "ecr:GetAuthorizationToken",
      "Resource": "*"
    }
  ]
}
```

```bash
aws iam put-role-policy \
  --role-name equicast-github-actions \
  --policy-name equicast-github-actions-permissions \
  --policy-document file://permissions-policy.json
```

**On the `s3:*`/`ecr:*` action wildcards**: true action-level least privilege
for Terraform-managed resources is fragile in practice — the AWS provider's
drift-detection reads a long, version-dependent list of `Get*`/`List*`
actions per resource, and hand-picking them tends to break on the next
provider upgrade. Scoping tightly by **resource** (only `equicast-*` named
buckets and repos, never the rest of the account) while allowing full
service actions *within* those resources is the pragmatic middle ground:
narrow enough that this role can't touch anything outside this project, but
not so brittle it breaks the next time `terraform plan` reads one more
attribute. `ecr:GetAuthorizationToken` is the one exception that must stay
`Resource: "*"` — AWS doesn't support resource-level scoping for it; it's
only used to authenticate `docker login`, not to act on any repository.

## Step 4: Wire it into the repo

- Settings → Secrets and variables → Actions → **New repository secret**:
  `AWS_ROLE_ARN` = `arn:aws:iam::<AWS_ACCOUNT_ID>:role/equicast-github-actions`
- Settings → Secrets and variables → Actions → **Variables** tab (optional):
  `AWS_REGION` if not `eu-west-1`

## Verifying it end-to-end

Run each workflow manually (Actions tab → pick the workflow → *Run
workflow*, where available) and check its "Configure AWS credentials"
(or equivalent) step succeeds with no error. `terraform.yml`'s `plan` job is
the easiest first check — it doesn't mutate anything.

## Troubleshooting

**`Not authorized to perform sts:AssumeRoleWithWebIdentity`** — the trust
policy's `sub` condition doesn't match. Check the repo name/org are exactly
right (case-sensitive) and that you're running from `coldsofttech/equiCast`
itself, not a fork (a fork has a different `repo:` claim).

**Creating the OIDC provider fails** (`EntityAlreadyExists`) — the account
already has one; skip Step 1 and reuse the existing provider's ARN in the
trust policy's `Federated` field.

**`configure-aws-credentials` fails with no OIDC token available** — the
job is missing `permissions: id-token: write`. This must be set explicitly
on every job that assumes the role; it isn't part of the default permission
set.

**`AccessDenied` on a specific S3/ECR action** — the resource name doesn't
match the `equicast-*` pattern the permissions policy scopes to, or it's a
service/action outside what's granted (e.g. IAM, EC2 — this role has none).

## Security notes

- The role trusts only this specific repo (`repo:coldsofttech/equiCast:*`),
  not the whole GitHub org or arbitrary repos.
- Permissions are scoped to `equicast-*` named S3 buckets and ECR
  repositories only — nothing else in the account is reachable.
- No credentials are stored anywhere: each workflow run gets its own
  short-lived token (~1 hour), and a new one is issued fresh on every run.

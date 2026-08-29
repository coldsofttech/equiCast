# Remote state storage. The bucket itself is bootstrapped once, out of band
# (same reasoning as the OIDC role in docs/aws-github-oidc-setup.md: Terraform
# can't be trusted to create the bucket that holds its own state). `key` is
# deliberately omitted here — it can't be interpolated with `var.environment`
# in a backend block, so it's supplied per environment via `-backend-config`
# at `terraform init` time (see terraform.yml's apply-dev/apply-prod jobs).
#
# use_lockfile uses Terraform's native S3 state locking (>= 1.10) instead of
# a DynamoDB table — one less resource to bootstrap and pay for.
terraform {
  backend "s3" {
    bucket       = "equicast-tf-state"
    region       = "eu-west-1"
    encrypt      = true
    use_lockfile = true
  }
}

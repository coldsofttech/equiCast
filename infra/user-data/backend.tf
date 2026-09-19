# Same remote state bucket as ../backend.tf, under a different `key` (per-
# environment, supplied via -backend-config at `terraform init` time — see
# that file's comment for why it can't be hardcoded here).
terraform {
  backend "s3" {
    bucket       = "equicast-tf-state"
    region       = "eu-west-1"
    encrypt      = true
    use_lockfile = true
  }
}

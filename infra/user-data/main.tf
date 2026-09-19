# Split into its own Terraform state so it can never be caught by a
# `terraform destroy` against ../main.tf's state. Terraform has no
# "-exclude" flag on any command (plan/apply included — see
# infra-lifecycle.yml's history), so the only way to keep one resource out
# of another root's destroy is to not have it in that root's state at all.
# This bucket holds real user data a redeploy can't recreate; everything
# in ../main.tf is disposable and gets torn down/rebuilt freely by
# infra-lifecycle.yml.
module "user_data_bucket" {
  source = "../modules/s3_bucket"

  bucket_name = "${var.project_name}-user-data-${var.environment}"
}

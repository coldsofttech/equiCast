# Remote state storage. Bootstrap this bucket/table once, out of band,
# then uncomment to enable remote state for this configuration.
#
# terraform {
#   backend "s3" {
#     bucket         = "equicast-terraform-state"
#     key            = "equicast/terraform.tfstate"
#     region         = "eu-west-1"
#     dynamodb_table = "equicast-terraform-locks"
#     encrypt        = true
#   }
# }

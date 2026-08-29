terraform {
  required_version = ">= 1.10" # S3 native state locking (backend.tf's use_lockfile)

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

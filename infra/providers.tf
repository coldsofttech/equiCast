terraform {
  required_version = ">= 1.10" # S3 native state locking (backend.tf's use_lockfile)

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      application = "equicast"
      environment = var.environment == "prod" ? "production" : "development"
    }
  }
}

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket         = "aegis-terraform-state-prod"
    key            = "master/prod/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "aegis-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "AEGIS"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "DisasterResponseOps"
    }
  }
}

variable "aws_region" {
  default = "ap-south-1"
}

variable "environment" {
  default = "production"
}

resource "aws_vpc" "aegis_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "aegis-${var.environment}-vpc" }
}

resource "aws_subnet" "public" {
  count                   = 3
  vpc_id                  = aws_vpc.aegis_vpc.id
  cidr_block              = "10.0.${count.index + 1}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  tags = { Name = "aegis-${var.environment}-public-${count.index + 1}" }
}

resource "aws_subnet" "private_app" {
  count             = 3
  vpc_id            = aws_vpc.aegis_vpc.id
  cidr_block        = "10.0.${count.index + 10}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]
  tags = { Name = "aegis-${var.environment}-private-app-${count.index + 1}" }
}

resource "aws_subnet" "private_db" {
  count             = 3
  vpc_id            = aws_vpc.aegis_vpc.id
  cidr_block        = "10.0.${count.index + 20}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]
  tags = { Name = "aegis-${var.environment}-private-db-${count.index + 1}" }
}

data "aws_availability_zones" "available" {
  state = "available"
}

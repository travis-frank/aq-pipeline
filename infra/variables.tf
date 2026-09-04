variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short name used in resource Name tags."
  type        = string
  default     = "aq-pipeline"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (one per AZ). No public subnets."
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]

  validation {
    condition     = length(var.private_subnet_cidrs) >= 2
    error_message = "Provide at least two private subnet CIDRs (RDS needs multi-AZ)."
  }
}

variable "availability_zones" {
  description = "Availability zones for private subnets. Length must match private_subnet_cidrs."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]

  validation {
    condition     = length(var.availability_zones) == length(var.private_subnet_cidrs)
    error_message = "availability_zones length must match private_subnet_cidrs."
  }
}

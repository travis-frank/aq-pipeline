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
  description = "CIDR blocks for private subnets (one per AZ)."
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]

  validation {
    condition     = length(var.private_subnet_cidrs) >= 2
    error_message = "Provide at least two private subnet CIDRs (RDS needs multi-AZ)."
  }
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (NAT Gateway)."
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24"]

  validation {
    condition     = length(var.public_subnet_cidrs) >= 1
    error_message = "Provide at least one public subnet CIDR for the NAT Gateway."
  }

  validation {
    condition     = length(var.public_subnet_cidrs) <= length(var.availability_zones)
    error_message = "public_subnet_cidrs length cannot exceed availability_zones."
  }
}

variable "availability_zones" {
  description = "Availability zones. Length must match private_subnet_cidrs; public subnets use the same list (truncated if fewer public CIDRs)."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]

  validation {
    condition     = length(var.availability_zones) == length(var.private_subnet_cidrs)
    error_message = "availability_zones length must match private_subnet_cidrs."
  }
}

variable "raw_bucket_name" {
  description = "Globally unique S3 bucket name for the raw OpenAQ landing zone. If null, a unique name is generated."
  type        = string
  default     = null
}

variable "db_identifier" {
  description = "RDS instance identifier."
  type        = string
  default     = "aq-pipeline"
}

variable "db_name" {
  description = "Initial Postgres database name on RDS."
  type        = string
  default     = "aq_pipeline"
}

variable "db_username" {
  description = "RDS master username."
  type        = string
  default     = "aq_user"
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t3.micro"
}

variable "airflow_image" {
  description = "Container image for Airflow tasks (ECR URI after Phase 5; apache/airflow for plan)."
  type        = string
  default     = "apache/airflow:2.9.3"
}

variable "airflow_cpu" {
  description = "Fargate CPU units for Airflow tasks."
  type        = string
  default     = "1024"
}

variable "airflow_memory" {
  description = "Fargate memory (MiB) for Airflow tasks."
  type        = string
  default     = "2048"
}

variable "openaq_api_key" {
  description = "OpenAQ API key stored in SSM SecureString. Required at apply; never commit a real key."
  type        = string
  sensitive   = true
}

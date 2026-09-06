# Raw landing zone for OpenAQ pulls. IAM for ECS is scoped to this bucket only.

resource "random_id" "raw_bucket_suffix" {
  byte_length = 4
}

locals {
  raw_bucket_name = coalesce(
    var.raw_bucket_name,
    "${var.project_name}-raw-${random_id.raw_bucket_suffix.hex}"
  )
}

resource "aws_s3_bucket" "raw" {
  bucket = local.raw_bucket_name

  tags = {
    Name = "${local.name}-raw"
    Tier = "raw"
  }
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket = aws_s3_bucket.raw.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

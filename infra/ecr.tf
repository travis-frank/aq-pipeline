# ECR repository for the custom Airflow image (openaq + dbt-postgres).
# force_delete lets terraform destroy succeed even if tags remain.

resource "aws_ecr_repository" "airflow" {
  name                 = "${local.name}-airflow"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = false
  }

  tags = {
    Name = "${local.name}-airflow"
  }
}

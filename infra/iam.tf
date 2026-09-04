# IAM for the Airflow ECS task — least privilege to the raw S3 bucket and
# this project's RDS instance only. No Resource = "*".

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "ecs_task_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "airflow_ecs_task" {
  name               = "${local.name}-airflow-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json

  tags = {
    Name = "${local.name}-airflow-ecs-task"
  }
}

data "aws_iam_policy_document" "airflow_ecs_task" {
  # Raw landing zone — this bucket only.
  statement {
    sid    = "RawBucketList"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [aws_s3_bucket.raw.arn]
  }

  statement {
    sid    = "RawObjectReadWrite"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["${aws_s3_bucket.raw.arn}/*"]
  }

  # Describe this RDS instance only (network access is enforced by SG).
  statement {
    sid    = "DescribeThisRdsInstance"
    effect = "Allow"
    actions = [
      "rds:DescribeDBInstances",
      "rds:ListTagsForResource",
    ]
    resources = [aws_db_instance.main.arn]
  }
}

resource "aws_iam_role_policy" "airflow_ecs_task" {
  name   = "${local.name}-airflow-ecs-task"
  role   = aws_iam_role.airflow_ecs_task.id
  policy = data.aws_iam_policy_document.airflow_ecs_task.json
}

# ECS task execution role — used by the ECS agent to pull images, write
# logs, and fetch SSM SecureString secrets into the container at start.
# Separate from airflow_ecs_task (application permissions to S3/RDS).

resource "aws_iam_role" "ecs_task_execution" {
  name               = "${local.name}-ecs-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json

  tags = {
    Name = "${local.name}-ecs-task-execution"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_kms_key" "ssm" {
  key_id = "alias/aws/ssm"
}

data "aws_iam_policy_document" "ecs_task_execution_ssm" {
  statement {
    sid    = "ReadTaskSecretsFromSsm"
    effect = "Allow"
    actions = [
      "ssm:GetParameters",
      "ssm:GetParameter",
    ]
    resources = [
      aws_ssm_parameter.db_password.arn,
      aws_ssm_parameter.openaq_api_key.arn,
      aws_ssm_parameter.airflow_fernet_key.arn,
      aws_ssm_parameter.airflow_sqlalchemy_conn.arn,
    ]
  }

  statement {
    sid    = "DecryptSsmSecureString"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
    ]
    resources = [data.aws_kms_key.ssm.arn]
  }
}

resource "aws_iam_role_policy" "ecs_task_execution_ssm" {
  name   = "${local.name}-ecs-task-execution-ssm"
  role   = aws_iam_role.ecs_task_execution.id
  policy = data.aws_iam_policy_document.ecs_task_execution_ssm.json
}

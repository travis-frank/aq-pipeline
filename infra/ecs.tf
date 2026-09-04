# ECS cluster + on-demand Fargate task definitions for Airflow.
#
# Three task definitions match local compose: init (one-shot), webserver,
# and scheduler. No ECS Service / autoscaling yet — run with
# `aws ecs run-task` during demos, then terraform destroy.
#
# Shared image/env/roles/network/log settings live in locals so the three
# definitions cannot drift.

resource "random_password" "airflow_fernet" {
  length  = 32
  special = false
}

resource "aws_cloudwatch_log_group" "airflow" {
  name              = "/ecs/${local.name}/airflow"
  retention_in_days = 7

  tags = {
    Name = "${local.name}-airflow-logs"
  }
}

resource "aws_ecs_cluster" "main" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = {
    Name = "${local.name}-ecs"
  }
}

locals {
  # Network placement for run-task (private subnets + ECS SG from 4.2).
  ecs_network = {
    subnets          = [for s in aws_subnet.private : s.id]
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  # Airflow metastore on the same RDS instance as the warehouse for this
  # ephemeral demo. Locally we use a separate `airflow` database; a dedicated
  # RDS database can be added in Phase 5 if needed.
  airflow_sqlalchemy_conn = format(
    "postgresql+psycopg2://%s:%s@%s:5432/%s",
    var.db_username,
    random_password.db.result,
    aws_db_instance.main.address,
    var.db_name,
  )

  airflow_environment = [
    { name = "AIRFLOW__CORE__EXECUTOR", value = "LocalExecutor" },
    { name = "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN", value = local.airflow_sqlalchemy_conn },
    { name = "AIRFLOW__CORE__FERNET_KEY", value = random_password.airflow_fernet.result },
    { name = "AIRFLOW__CORE__LOAD_EXAMPLES", value = "false" },
    { name = "AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION", value = "true" },
    { name = "AIRFLOW__WEBSERVER__EXPOSE_CONFIG", value = "false" },
    { name = "AIRFLOW__SCHEDULER__ENABLE_HEALTH_CHECK", value = "true" },
    { name = "DB_HOST", value = aws_db_instance.main.address },
    { name = "DB_PORT", value = "5432" },
    { name = "DB_NAME", value = var.db_name },
    { name = "DB_USER", value = var.db_username },
    { name = "DB_PASSWORD", value = random_password.db.result },
  ]

  airflow_log_config = {
    logDriver = "awslogs"
    options = {
      "awslogs-group"         = aws_cloudwatch_log_group.airflow.name
      "awslogs-region"        = var.aws_region
      "awslogs-stream-prefix" = "airflow"
    }
  }

  airflow_container_base = {
    image            = var.airflow_image
    essential        = true
    environment      = local.airflow_environment
    logConfiguration = local.airflow_log_config
  }
}

resource "aws_ecs_task_definition" "airflow_init" {
  family                   = "${local.name}-airflow-init"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.airflow_cpu
  memory                   = var.airflow_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.airflow_ecs_task.arn

  container_definitions = jsonencode([
    merge(local.airflow_container_base, {
      name = "airflow-init"
      command = [
        "bash",
        "-c",
        <<-EOT
          set -e
          airflow db migrate
          airflow users create \
            --username admin \
            --password admin \
            --firstname Admin \
            --lastname User \
            --role Admin \
            --email admin@example.com \
            || true
        EOT
      ]
    })
  ])

  tags = {
    Name = "${local.name}-airflow-init"
  }
}

resource "aws_ecs_task_definition" "airflow_webserver" {
  family                   = "${local.name}-airflow-webserver"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.airflow_cpu
  memory                   = var.airflow_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.airflow_ecs_task.arn

  container_definitions = jsonencode([
    merge(local.airflow_container_base, {
      name    = "airflow-webserver"
      command = ["webserver"]
      portMappings = [
        {
          containerPort = 8080
          hostPort      = 8080
          protocol      = "tcp"
        }
      ]
    })
  ])

  tags = {
    Name = "${local.name}-airflow-webserver"
  }
}

resource "aws_ecs_task_definition" "airflow_scheduler" {
  family                   = "${local.name}-airflow-scheduler"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.airflow_cpu
  memory                   = var.airflow_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.airflow_ecs_task.arn

  container_definitions = jsonencode([
    merge(local.airflow_container_base, {
      name    = "airflow-scheduler"
      command = ["scheduler"]
    })
  ])

  tags = {
    Name = "${local.name}-airflow-scheduler"
  }
}

# Security groups — no 0.0.0.0/0 ingress anywhere.
# ECS may egress to the internet via NAT (OpenAQ API + image pulls).
# RDS accepts Postgres only from the ECS task security group.

resource "aws_security_group" "ecs_tasks" {
  name        = "${local.name}-ecs-tasks"
  description = "Airflow / pipeline ECS tasks in private subnets"
  vpc_id      = aws_vpc.main.id

  # No inbound from the internet. Intra-VPC / self traffic can be added later
  # if the API or Airflow web UI needs it.
  egress {
    description = "Outbound via NAT (OpenAQ API, ECR image pulls, etc.)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name}-ecs-tasks"
  }
}

resource "aws_security_group" "rds" {
  name        = "${local.name}-rds"
  description = "RDS Postgres — ingress only from ECS tasks"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Postgres from ECS tasks only"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  # No broad egress needed for RDS; allow VPC-local responses only.
  egress {
    description = "Allow responses within the VPC"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = {
    Name = "${local.name}-rds"
  }
}

# Warehouse RDS — private subnets only, reachable solely from the ECS SG.
# Created here so IAM can attach to this specific instance ARN (no "*").

resource "random_password" "db" {
  length  = 32
  special = false
}

resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-db"
  subnet_ids = [for s in aws_subnet.private : s.id]

  tags = {
    Name = "${local.name}-db-subnets"
  }
}

resource "aws_db_instance" "main" {
  identifier = var.db_identifier

  engine                = "postgres"
  engine_version        = "15"
  instance_class        = var.db_instance_class
  allocated_storage     = 20
  max_allocated_storage = 50

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = false

  skip_final_snapshot = true
  deletion_protection = false
  apply_immediately   = true

  tags = {
    Name = "${local.name}-rds"
  }
}

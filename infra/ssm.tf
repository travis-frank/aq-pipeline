# SSM Parameter Store (SecureString) for secrets injected into ECS tasks.
# Chosen over Secrets Manager: free, no rotation needed for ephemeral demos.
# Values come from Terraform variables / random providers — never hardcode.

resource "aws_ssm_parameter" "db_password" {
  name        = "/${local.name}/DB_PASSWORD"
  description = "RDS master password for ${local.name}"
  type        = "SecureString"
  value       = random_password.db.result

  tags = {
    Name = "${local.name}-db-password"
  }
}

resource "aws_ssm_parameter" "openaq_api_key" {
  name        = "/${local.name}/OPENAQ_API_KEY"
  description = "OpenAQ API key for ${local.name} ingestion"
  type        = "SecureString"
  value       = var.openaq_api_key

  tags = {
    Name = "${local.name}-openaq-api-key"
  }
}

resource "aws_ssm_parameter" "airflow_fernet_key" {
  name        = "/${local.name}/AIRFLOW__CORE__FERNET_KEY"
  description = "Airflow Fernet key for ${local.name}"
  type        = "SecureString"
  value       = random_password.airflow_fernet.result

  tags = {
    Name = "${local.name}-airflow-fernet-key"
  }
}

# SQLAlchemy URI embeds the DB password — must not live in the ECS
# task definition environment block as plaintext.
resource "aws_ssm_parameter" "airflow_sqlalchemy_conn" {
  name        = "/${local.name}/AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"
  description = "Airflow metastore SQLAlchemy connection URI"
  type        = "SecureString"
  value       = local.airflow_sqlalchemy_conn

  tags = {
    Name = "${local.name}-airflow-sqlalchemy-conn"
  }
}

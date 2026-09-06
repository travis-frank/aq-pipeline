output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "IDs of private subnets (RDS, ECS)."
  value       = [for s in aws_subnet.private : s.id]
}

output "public_subnet_ids" {
  description = "IDs of public subnets (NAT Gateway)."
  value       = [for s in aws_subnet.public : s.id]
}

output "nat_gateway_id" {
  description = "NAT Gateway ID (ephemeral — destroyed with terraform destroy)."
  value       = aws_nat_gateway.main.id
}

output "private_route_table_id" {
  description = "Private route table ID (S3 gateway endpoint + NAT default route)."
  value       = aws_route_table.private.id
}

output "s3_vpc_endpoint_id" {
  description = "Gateway VPC endpoint for S3."
  value       = aws_vpc_endpoint.s3.id
}

output "raw_bucket_name" {
  description = "Raw landing-zone S3 bucket name."
  value       = aws_s3_bucket.raw.id
}

output "raw_bucket_arn" {
  description = "Raw landing-zone S3 bucket ARN."
  value       = aws_s3_bucket.raw.arn
}

output "rds_endpoint" {
  description = "RDS Postgres endpoint address."
  value       = aws_db_instance.main.address
}

output "rds_arn" {
  description = "RDS instance ARN (IAM is scoped to this)."
  value       = aws_db_instance.main.arn
}

output "ecs_tasks_security_group_id" {
  description = "Security group for ECS tasks."
  value       = aws_security_group.ecs_tasks.id
}

output "rds_security_group_id" {
  description = "Security group for RDS."
  value       = aws_security_group.rds.id
}

output "airflow_ecs_task_role_arn" {
  description = "IAM role ARN for the Airflow ECS task (S3/RDS app permissions)."
  value       = aws_iam_role.airflow_ecs_task.arn
}

output "ecs_task_execution_role_arn" {
  description = "IAM role ARN for ECS task execution (ECR pull + CloudWatch logs)."
  value       = aws_iam_role.ecs_task_execution.arn
}

output "ecs_cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  description = "ECS cluster ARN."
  value       = aws_ecs_cluster.main.arn
}

output "airflow_task_definition_arns" {
  description = "Airflow Fargate task definition ARNs (init, webserver, scheduler)."
  value = {
    init      = aws_ecs_task_definition.airflow_init.arn
    webserver = aws_ecs_task_definition.airflow_webserver.arn
    scheduler = aws_ecs_task_definition.airflow_scheduler.arn
  }
}

output "ecs_run_task_network_configuration" {
  description = "Network config for aws ecs run-task (private subnets + ECS SG)."
  value       = local.ecs_network
}

output "billing_sns_topic_arn" {
  description = "SNS topic for the $5 billing alarm (us-east-1). Subscribe manually if billing_alert_email is unset."
  value       = aws_sns_topic.billing.arn
}

output "ops_sns_topic_arn" {
  description = "SNS topic for RDS CPU/storage alarms."
  value       = aws_sns_topic.ops.arn
}

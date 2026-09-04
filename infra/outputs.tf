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
  description = "IAM role ARN for the Airflow ECS task."
  value       = aws_iam_role.airflow_ecs_task.arn
}

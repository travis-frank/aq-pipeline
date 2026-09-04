output "vpc_id" {
  description = "ID of the private-only VPC."
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "IDs of private subnets (for RDS, ECS, etc.)."
  value       = [for s in aws_subnet.private : s.id]
}

output "private_route_table_id" {
  description = "Private route table ID (S3 gateway endpoint is associated here)."
  value       = aws_route_table.private.id
}

output "s3_vpc_endpoint_id" {
  description = "Gateway VPC endpoint for S3."
  value       = aws_vpc_endpoint.s3.id
}

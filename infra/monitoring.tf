# CloudWatch alarms: RDS health + monthly spend cap.
#
# Billing metrics (AWS/Billing) are only published in us-east-1, so the
# billing alarm and its SNS topic use a dedicated provider alias. Confirm
# "Receive Billing Alerts" is enabled in the account billing preferences
# or the EstimatedCharges metric will be missing.

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "terraform"
    }
  }
}

variable "billing_alert_email" {
  description = "Email for the $5 billing alarm SNS subscription. Null = topic only (subscribe manually)."
  type        = string
  default     = null
}

variable "rds_cpu_alarm_threshold" {
  description = "RDS CPUUtilization alarm threshold (percent)."
  type        = number
  default     = 80
}

variable "rds_free_storage_alarm_bytes" {
  description = "Alarm when RDS FreeStorageSpace falls below this many bytes (default 2 GiB)."
  type        = number
  default     = 2147483648
}

variable "billing_alarm_threshold_usd" {
  description = "Monthly EstimatedCharges alarm threshold in USD."
  type        = number
  default     = 5
}

# --- SNS (us-east-1) for billing ------------------------------------------------

resource "aws_sns_topic" "billing" {
  provider = aws.us_east_1
  name     = "${local.name}-billing-alerts"

  tags = {
    Name = "${local.name}-billing-alerts"
  }
}

resource "aws_sns_topic_subscription" "billing_email" {
  count = var.billing_alert_email != null ? 1 : 0

  provider  = aws.us_east_1
  topic_arn = aws_sns_topic.billing.arn
  protocol  = "email"
  endpoint  = var.billing_alert_email
}

# --- Billing alarm ($5 / month) -------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "billing" {
  provider = aws.us_east_1

  alarm_name          = "${local.name}-billing-over-${var.billing_alarm_threshold_usd}"
  alarm_description   = "Estimated AWS charges exceeded ${var.billing_alarm_threshold_usd} USD this month"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = 21600
  statistic           = "Maximum"
  threshold           = var.billing_alarm_threshold_usd
  treat_missing_data  = "notBreaching"

  dimensions = {
    Currency = "USD"
  }

  alarm_actions = [aws_sns_topic.billing.arn]
  ok_actions    = [aws_sns_topic.billing.arn]

  tags = {
    Name = "${local.name}-billing-alarm"
  }
}

# --- RDS alarms (workload region) ----------------------------------------------

resource "aws_sns_topic" "ops" {
  name = "${local.name}-ops-alerts"

  tags = {
    Name = "${local.name}-ops-alerts"
  }
}

resource "aws_sns_topic_subscription" "ops_email" {
  count = var.billing_alert_email != null ? 1 : 0

  topic_arn = aws_sns_topic.ops.arn
  protocol  = "email"
  endpoint  = var.billing_alert_email
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${local.name}-rds-cpu-high"
  alarm_description   = "RDS CPUUtilization above ${var.rds_cpu_alarm_threshold}%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = var.rds_cpu_alarm_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }

  alarm_actions = [aws_sns_topic.ops.arn]
  ok_actions    = [aws_sns_topic.ops.arn]

  tags = {
    Name = "${local.name}-rds-cpu-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_storage" {
  alarm_name          = "${local.name}-rds-storage-low"
  alarm_description   = "RDS FreeStorageSpace below ${var.rds_free_storage_alarm_bytes} bytes"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = var.rds_free_storage_alarm_bytes
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }

  alarm_actions = [aws_sns_topic.ops.arn]
  ok_actions    = [aws_sns_topic.ops.arn]

  tags = {
    Name = "${local.name}-rds-storage-alarm"
  }
}

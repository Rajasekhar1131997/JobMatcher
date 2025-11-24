variable "region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "jobmatcher"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "github_role_arn" {
  description = "ARN of the GitHub OIDC role"
  type        = string
  sensitive   = true
}

variable "domain_name" {
  description = "Domain name for SSL and routes"
  type        = string
  default     = "example.com"  # Replace with actual domain
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    Project     = "JobMatcher"
    Environment = "dev"
    Owner       = "Team"
  }
}

variable "db_username" {
  description = "Database username"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

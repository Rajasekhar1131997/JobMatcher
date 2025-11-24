variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "eks_version" {
  description = "EKS cluster version"
  type        = string
  default     = "1.29"
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs"
  type        = list(string)
}

variable "default_security_group_id" {
  description = "Default security group ID"
  type        = string
}

variable "desired_capacity" {
  description = "Desired number of worker nodes"
  type        = number
  default     = 2
}

variable "min_capacity" {
  description = "Minimum number of worker nodes"
  type        = number
  default     = 1
}

variable "max_capacity" {
  description = "Maximum number of worker nodes"
  type        = number
  default     = 4
}

variable "instance_types" {
  description = "List of EC2 instance types for nodes"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "ami_type" {
  description = "AMI type for nodes"
  type        = string
  default     = "AL2_x86_64"
}

variable "disk_size" {
  description = "Disk size for nodes in GB"
  type        = number
  default     = 20
}

variable "tags" {
  description = "Common tags"
  type        = map(string)
}

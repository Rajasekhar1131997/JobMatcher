locals {
  public_subnets = [
    cidrsubnet(var.vpc_cidr, 8, 1),  # 10.0.1.0/24
    cidrsubnet(var.vpc_cidr, 8, 2),  # 10.0.2.0/24
    cidrsubnet(var.vpc_cidr, 8, 3),  # 10.0.3.0/24
  ]

  private_subnets = [
    cidrsubnet(var.vpc_cidr, 8, 101),  # 10.0.101.0/24
    cidrsubnet(var.vpc_cidr, 8, 102),  # 10.0.102.0/24
    cidrsubnet(var.vpc_cidr, 8, 103),  # 10.0.103.0/24
  ]
}

module "vpc" {
  source = "../modules/vpc"

  vpc_cidr        = var.vpc_cidr
  public_subnets  = local.public_subnets
  private_subnets = local.private_subnets
  azs             = var.availability_zones
  project_name    = var.project_name
  tags            = var.tags
}

module "eks" {
  source = "../modules/eks"

  project_name              = var.project_name
  environment               = var.environment
  eks_version               = "1.29"
  private_subnet_ids        = module.vpc.private_subnet_ids
  default_security_group_id = module.vpc.default_security_group_id
  desired_capacity          = 2
  min_capacity              = 1
  max_capacity              = 4
  instance_types            = ["t3.medium"]
  tags                      = var.tags
}

module "rds" {
  source = "../modules/rds"

  project_name         = var.project_name
  vpc_id               = module.vpc.vpc_id
  private_subnet_ids   = module.vpc.private_subnet_ids
  eks_security_group_id = module.vpc.default_security_group_id  # Assuming this allows access, may need specific SG
  db_name              = "jobmatcher"
  db_username          = var.db_username
  db_password          = var.db_password
  tags                 = var.tags
}

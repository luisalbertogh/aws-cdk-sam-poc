#!/usr/bin/env python3
"""
CDK application entry point for the Cloud POC infrastructure.

Target account/region are resolved from environment variables injected by
GitHub Actions (AWS_ACCOUNT_ID / CDK_DEFAULT_REGION) or the CDK CLI.
"""

import os

import aws_cdk as cdk

from config import COMMON_TAGS
from config.ecs_config import CHEF_UI_ECS_CONFIG
from stacks import ClusterStack, EcsStack, NetworkStack, OrchestrationStack, RegistryStack, SecretsStack, StorageStack

app = cdk.App()

# ---------------------------------------------------------------------------
# Environment — account and region are resolved from the caller identity.
# When CDK_DEFAULT_REGION is unset the stack is environment-agnostic and
# the region is resolved at deploy time.
# ---------------------------------------------------------------------------
env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT", os.environ.get("AWS_ACCOUNT_ID")),
    region=os.environ.get("CDK_DEFAULT_REGION"),
)

network_stack = NetworkStack(
    app,
    "CloudPocNetworkStack",
    env=env,
    description="Cloud POC — VPC, public subnets, IGW and security group",
)

StorageStack(
    app,
    "CloudPocStorageStack",
    env=env,
    description="Cloud POC — private encrypted S3 bucket",
)

# ---------------------------------------------------------------------------
# ECS Cluster — created before SecretsStack
# This ensures the cluster and execution role exist before any dependent
# resources are created.
# ---------------------------------------------------------------------------
cluster_stack = ClusterStack(
    app,
    "CloudPocClusterStack",
    vpc=network_stack.vpc,
    env=env,
    description="Cloud POC — ECS cluster for Chef UI",
)

registry_stack = RegistryStack(
    app,
    "CloudPocRegistryStack",
    env=env,
    description="Cloud POC — private ECR repository for chef-assistant images",
)

secrets_stack = SecretsStack(
    app,
    "CloudPocSecretsStack",
    secret_name=CHEF_UI_ECS_CONFIG.login_secret_name,
    #reader_role_arn=cluster_stack.execution_role.role_arn,
    env=env,
    description="Cloud POC — Secrets Manager secrets for Chef UI",
)

orchestration_stack = OrchestrationStack(
    app,
    "CloudPocOrchestrationStack",
    env=env,
    description="Cloud POC — Hello World Step Functions workflow",
)

EcsStack(
    app,
    "CloudPocEcsStack",
    vpc=network_stack.vpc,
    security_group=network_stack.security_group,
    cluster=cluster_stack.cluster,    
    execution_role=cluster_stack.execution_role,    
    chef_ui_repository=registry_stack.repositories["chef-ui"],
    login_secret=secrets_stack.login_secret,
    state_machine_arn=orchestration_stack.state_machine.state_machine_arn,
    env=env,
    description="Cloud POC — Chef UI ECS Fargate service",
)

# ---------------------------------------------------------------------------
# Global tags — applied to every resource in every stack.
# Edit config/tags_config.py to change values.
# ---------------------------------------------------------------------------
for key, value in COMMON_TAGS.items():
    cdk.Tags.of(app).add(key, value)

app.synth()

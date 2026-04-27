#!/usr/bin/env python3
"""
CDK application entry point for the AgentCore POC infrastructure.

Target account/region is provided via CDK context or environment variables
injected by GitHub Actions (AWS_ACCOUNT_ID / CDK_DEFAULT_REGION).
"""

import os

import aws_cdk as cdk

from config import COMMON_TAGS
from config.ecs_config import CHEF_UI_ECS_CONFIG
from stacks import ComputeStack, EcsStack, NetworkStack, OrchestrationStack, RegistryStack, SecretsStack, StorageStack

app = cdk.App()

# ---------------------------------------------------------------------------
# Environment — region is pinned; account is resolved from the caller identity
# that GitHub Actions assumes via OIDC federation.
# ---------------------------------------------------------------------------
env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT", os.environ.get("AWS_ACCOUNT_ID")),
    region=os.environ.get("CDK_DEFAULT_REGION", "eu-central-1"),
)

network_stack = NetworkStack(
    app,
    "AgentCorePocNetworkStack",
    env=env,
    description="AgentCore POC — VPC, public subnets, IGW and security group (eu-central-1)",
)

StorageStack(
    app,
    "AgentCorePocStorageStack",
    env=env,
    description="AgentCore POC — private encrypted S3 bucket (eu-central-1)",
)

registry_stack = RegistryStack(
    app,
    "AgentCorePocRegistryStack",
    env=env,
    description="AgentCore POC — private ECR repository for chef-assistant images (eu-central-1)",
)

compute_stack = ComputeStack(
    app,
    "AgentCorePocComputeStack",
    registry_stack=registry_stack,
    env=env,
    description="AgentCore POC — AgentCore Gateway ChefAssistantGateway and OpenFoodFactsAPI Lambda function",
)

secrets_stack = SecretsStack(
    app,
    "AgentCorePocSecretsStack",
    secret_name=CHEF_UI_ECS_CONFIG.login_secret_name,
    reader_role_arn=CHEF_UI_ECS_CONFIG.task_execution_role_arn,
    env=env,
    description="AgentCore POC — Secrets Manager secrets for Chef UI (eu-central-1)",
)

orchestration_stack = OrchestrationStack(
    app,
    "AgentCorePocOrchestrationStack",
    compute_stack=compute_stack,
    env=env,
    description="AgentCore POC — Hello World Step Functions workflow with AgentCore Runtime invocation permissions (eu-central-1)",
)

EcsStack(
    app,
    "AgentCorePocEcsStack",
    vpc=network_stack.vpc,
    security_group=network_stack.security_group,
    chef_ui_repository=registry_stack.repositories["chef-ui"],
    login_secret=secrets_stack.login_secret,
    agent_runtime_arns=[r.agent_runtime_arn for r in compute_stack.runtimes.values()],
    state_machine_arn=orchestration_stack.state_machine.state_machine_arn,
    env=env,
    description="AgentCore POC — Chef UI ECS Fargate service (eu-central-1)",
)

# ---------------------------------------------------------------------------
# Global tags — applied to every resource in every stack.
# Edit config/tags_config.py to change values.
# ---------------------------------------------------------------------------
for key, value in COMMON_TAGS.items():
    cdk.Tags.of(app).add(key, value)

app.synth()

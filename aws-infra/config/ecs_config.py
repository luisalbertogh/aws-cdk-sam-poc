"""
ECS Fargate configuration for the Chef UI service.

All ECS/Fargate settings are centralised here so that the stack remains
policy-agnostic and configuration changes never require touching construct code.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EcsServiceConfig:
    """Immutable configuration for the Chef UI ECS Fargate service."""

    # ---------------------------------------------------------------------------
    # Container image
    # ---------------------------------------------------------------------------
    # ECR repository name that holds the chef-ui Docker image.
    ecr_repository_name: str = "chef-ui"

    # Image tag to pull. "latest" is used here; CI can override via context.
    image_tag: str = "latest"

    # ---------------------------------------------------------------------------
    # Task sizing
    # ---------------------------------------------------------------------------
    # 0.5 vCPU expressed as 512 CPU units (1 vCPU = 1024 units).
    cpu: int = 512

    # 2 GB of memory in MiB.
    memory_limit_mib: int = 2048

    # ---------------------------------------------------------------------------
    # Port mapping
    # ---------------------------------------------------------------------------
    # The Chainlit app listens on 8080 inside the container.
    container_port: int = 8080

    # Host (EC2 / bridge-mode) port that maps to container_port.
    # NOTE: Fargate tasks run in awsvpc network mode, which requires
    # host_port == container_port.  Setting a different value here will cause
    # CloudFormation to reject the task definition at deploy time.  For Fargate,
    # either set host_port equal to container_port or omit it entirely (CDK
    # defaults to the same value as container_port).
    host_port: int = 8080

    # ---------------------------------------------------------------------------
    # Service
    # ---------------------------------------------------------------------------
    # Number of desired task replicas.
    desired_count: int = 1

    # ---------------------------------------------------------------------------
    # Logging
    # ---------------------------------------------------------------------------
    # Retention period (in days) for the CloudWatch log group.
    log_retention_days: int = 7

    # ---------------------------------------------------------------------------
    # IAM
    # ---------------------------------------------------------------------------
    # ARN of the existing ECS task execution role that is allowed to pull images
    # from ECR and write CloudWatch logs.  This role already exists in the account
    # and is reused to avoid creating a duplicate.
    task_execution_role_arn: str = (
        "arn:aws:iam::741881499996:role/ecsTaskExecutionRole"
    )

    # ---------------------------------------------------------------------------
    # Secrets Manager
    # ---------------------------------------------------------------------------
    # Name of the Secrets Manager secret that holds the Chainlit auth credentials.
    # The secret is created empty by the stack; its JSON value must be populated
    # manually with the following fields: CHAINLIT_AUTH_SECRET, CHEF_UI_USER,
    # CHEF_UI_PASSWORD.
    login_secret_name: str = "chef-ui-login-passwords"

    # ---------------------------------------------------------------------------
    # Removal policy
    # ---------------------------------------------------------------------------
    # DESTROY is safe for ECS resources since they hold no persistent data.
    removal_policy: str = "DESTROY"


# ---------------------------------------------------------------------------
# Singleton instance consumed by the stack
# ---------------------------------------------------------------------------
CHEF_UI_ECS_CONFIG = EcsServiceConfig()

"""
ECR repository configuration for the AgentCore POC infrastructure.

All ECR settings are centralised here so that the stack remains
policy-agnostic and configuration changes never require touching
construct code.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EcrRepositoryConfig:
    """Immutable configuration for an AgentCore POC ECR repository."""

    # ---------------------------------------------------------------------------
    # Repository identity
    # ---------------------------------------------------------------------------
    # Explicit name so the AgentCore Runtime resource policy can reference it
    # by a predictable ARN without cross-stack exports.
    repository_name: str = "chef-agent"

    # ---------------------------------------------------------------------------
    # Visibility
    # ---------------------------------------------------------------------------
    # Private is the default and only supported value for this workload.
    # (Public repositories live in us-east-1 only; not applicable here.)

    # ---------------------------------------------------------------------------
    # Tag immutability
    # ---------------------------------------------------------------------------
    # Prevents overwriting an existing image tag. Enforces traceability and
    # prevents silent image replacement, which is an AWS-recommended security
    # practice.
    tag_immutability: bool = False

    # ---------------------------------------------------------------------------
    # Image scan on push
    # ---------------------------------------------------------------------------
    # Basic scan is free and flags known CVEs on every push.
    scan_on_push: bool = True

    # ---------------------------------------------------------------------------
    # Lifecycle policy
    # ---------------------------------------------------------------------------
    # Number of days after which *untagged* images are automatically expired.
    # Tagged images (i.e. release candidates) are never affected.
    untagged_expiry_days: int = 1

    # ---------------------------------------------------------------------------
    # Removal policy
    # ---------------------------------------------------------------------------
    # RETAIN keeps the repository (and all images) when the stack is deleted.
    # Change to "DESTROY" only in ephemeral / dev environments — note that
    # CDK requires the repository to be empty before it can delete it.
    removal_policy: str = "RETAIN"


# ---------------------------------------------------------------------------
# Per-agent repository configurations consumed by the stack
# ---------------------------------------------------------------------------
CHEF_AGENT_ECR_CONFIG = EcrRepositoryConfig(repository_name="chef-agent")
NUTRITIONIST_AGENT_ECR_CONFIG = EcrRepositoryConfig(repository_name="nutritionist-agent")
INSTRUCTOR_AGENT_ECR_CONFIG = EcrRepositoryConfig(repository_name="instructor-agent")
CHEF_UI_ECR_CONFIG = EcrRepositoryConfig(repository_name="chef-ui")

# Kept for backwards compatibility — points to the chef-agent repository.
AGENTCORE_ECR_CONFIG = CHEF_AGENT_ECR_CONFIG

# Nova Model IDs (Amazon Bedrock)
NOVA_MODEL_ID = "amazon.nova-2-lite-v1:0"

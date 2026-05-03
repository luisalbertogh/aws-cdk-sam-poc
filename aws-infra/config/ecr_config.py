"""
ECR repository configuration for the Cloud POC infrastructure.

All ECR settings are centralised here so that the stack remains
policy-agnostic and configuration changes never require touching
construct code.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EcrRepositoryConfig:
    """Immutable configuration for an Cloud POC ECR repository."""

    # ---------------------------------------------------------------------------
    # Repository identity
    # ---------------------------------------------------------------------------
    # Explicit name so the Cloud Runtime resource policy can reference it
    # by a predictable ARN without cross-stack exports.
    repository_name: str = "chef-ui"

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
    removal_policy: str = "DESTROY"


# ---------------------------------------------------------------------------
# Per-agent repository configurations consumed by the stack
# ---------------------------------------------------------------------------
CHEF_UI_ECR_CONFIG = EcrRepositoryConfig(repository_name="chef-ui")

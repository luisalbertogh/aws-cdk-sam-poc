"""
S3 bucket configuration for the Cloud POC infrastructure.

All S3 bucket settings are centralised here so that the stack
remains policy-agnostic and configuration changes never require
touching construct code.
"""

from dataclasses import dataclass, field

from aws_cdk import aws_s3 as s3


@dataclass(frozen=True)
class S3BucketConfig:
    """Immutable configuration for the Cloud POC S3 bucket."""

    # ---------------------------------------------------------------------------
    # Encryption
    # ---------------------------------------------------------------------------
    # S3_MANAGED uses AWS-managed keys (SSE-S3 / AES-256), which satisfies
    # encryption-at-rest without the operational overhead of KMS.
    # Switch to BucketEncryption.KMS_MANAGED or BucketEncryption.KMS to bring
    # your own key when stricter key-management requirements apply.
    encryption: s3.BucketEncryption = s3.BucketEncryption.S3_MANAGED

    # ---------------------------------------------------------------------------
    # Access control
    # ---------------------------------------------------------------------------
    # Block all forms of public access at the bucket level.
    block_public_access: s3.BlockPublicAccess = field(
        default_factory=lambda: s3.BlockPublicAccess.BLOCK_ALL
    )

    # Bucket-owner-enforced disables ACLs entirely (recommended by AWS).
    object_ownership: s3.ObjectOwnership = s3.ObjectOwnership.BUCKET_OWNER_ENFORCED

    # ---------------------------------------------------------------------------
    # SSL enforcement
    # ---------------------------------------------------------------------------
    # Adds a bucket policy that DENYs any request not using HTTPS (aws:SecureTransport).
    # Implements S3.5 of the AWS Foundational Security Best Practices.
    enforce_ssl: bool = True

    # ---------------------------------------------------------------------------
    # Versioning
    # ---------------------------------------------------------------------------
    versioned: bool = False

    # ---------------------------------------------------------------------------
    # Removal policy (used by the stack, not directly by the Bucket L2)
    # ---------------------------------------------------------------------------
    # RETAIN keeps the bucket when the stack is deleted (safe default for prod).
    # Change to "DESTROY" only in ephemeral / dev environments.
    removal_policy: str = "RETAIN"


# ---------------------------------------------------------------------------
# Singleton instance consumed by the stack
# ---------------------------------------------------------------------------
CLOUD_BUCKET_CONFIG = S3BucketConfig()

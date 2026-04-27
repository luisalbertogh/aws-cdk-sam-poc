"""
StorageStack — deploys the AgentCore POC S3 bucket.

Design decisions
----------------
- No explicit bucket name: CDK generates a unique, collision-free name via
  CloudFormation so the stack can be deployed multiple times without conflicts.
- Encryption at rest: SSE-S3 (AES-256) via AWS-managed keys as configured in
  config/s3_config.py.
- Private access: BlockPublicAccess.BLOCK_ALL + BUCKET_OWNER_ENFORCED ownership.
- SSL enforcement: enforce_ssl=True emits a bucket policy statement that denies
  any request where aws:SecureTransport is false (S3.5 AWS Foundational Security
  Best Practices).
- No versioning: versioned=False.
- No lifecycle rules: intentionally omitted per requirements.
"""

import aws_cdk as cdk
from aws_cdk import aws_s3 as s3
from constructs import Construct

from config import AGENTCORE_BUCKET_CONFIG


class StorageStack(cdk.Stack):
    """CDK stack that provisions the AgentCore POC S3 bucket."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cfg = AGENTCORE_BUCKET_CONFIG

        removal_policy = (
            cdk.RemovalPolicy.RETAIN
            if cfg.removal_policy == "RETAIN"
            else cdk.RemovalPolicy.DESTROY
        )

        self.bucket = s3.Bucket(
            self,
            "AgentCoreBucket",
            # --- Encryption at rest ---
            encryption=cfg.encryption,
            # --- Private access ---
            block_public_access=cfg.block_public_access,
            object_ownership=cfg.object_ownership,
            # --- SSL enforcement (adds deny-non-HTTPS bucket policy) ---
            enforce_ssl=cfg.enforce_ssl,
            # --- No versioning ---
            versioned=cfg.versioned,
            # --- Removal behaviour ---
            removal_policy=removal_policy,
        )

        # -----------------------------------------------------------------------
        # Outputs — useful for cross-stack references and CI verification
        # -----------------------------------------------------------------------
        cdk.CfnOutput(
            self,
            "BucketName",
            value=self.bucket.bucket_name,
            description="Name of the AgentCore POC S3 bucket",
            export_name=f"{self.stack_name}-BucketName",
        )

        cdk.CfnOutput(
            self,
            "BucketArn",
            value=self.bucket.bucket_arn,
            description="ARN of the AgentCore POC S3 bucket",
            export_name=f"{self.stack_name}-BucketArn",
        )

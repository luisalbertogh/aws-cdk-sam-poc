"""
RegistryStack — deploys the Cloud POC ECR repositories.

Design decisions
----------------
- Explicit repository names ("chef-agent", "nutritionist-agent",
  "instructor-agent"): Cloud Runtime resource policies reference each
  repository by ARN, so predictable names are required.
- Private visibility: enforced by default in ECR; no public access possible.
- Tag immutability: prevents silent overwrite of existing image tags, which is
  an AWS-recommended security and traceability best practice.
- Image scan on push: basic CVE scan at no extra cost on every pushed image.
- Lifecycle policy: untagged images (intermediate build layers, failed pushes)
  are expired after 1 day. Tagged images are never affected.
- Repository resource policy: grants bedrock-agentcore.amazonaws.com the minimum
  permissions required to pull images at runtime
  (ecr:BatchGetImage, ecr:GetDownloadUrlForLayer, ecr:GetAuthorizationToken).
- Removal policy: RETAIN (safe default; prevents accidental image loss on stack
  deletion).
"""

import aws_cdk as cdk
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_iam as iam
from constructs import Construct

from config import (
    CHEF_UI_ECR_CONFIG
)


# Mapping of logical construct ID prefix → config for each agent repository.
_AGENT_REPOS = [
    ("ChefUi", CHEF_UI_ECR_CONFIG),
]


class RegistryStack(cdk.Stack):
    """CDK stack that provisions the Cloud POC ECR repositories."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.repositories: dict[str, ecr.IRepository] = {}

        for logical_prefix, cfg in _AGENT_REPOS:
            repo = ecr.Repository(
                self,
                f"{logical_prefix}Repository",
                repository_name=cfg.repository_name,
                image_scan_on_push=cfg.scan_on_push,
                image_tag_mutability=(
                    ecr.TagMutability.IMMUTABLE if cfg.tag_immutability 
                    else ecr.TagMutability.MUTABLE
                ),
                # Ensure removal_policy is a cdk.RemovalPolicy object
                removal_policy=(
                    cdk.RemovalPolicy.DESTROY if cfg.removal_policy == "DESTROY" 
                    else cdk.RemovalPolicy.RETAIN
                ),
                lifecycle_rules=[
                    ecr.LifecycleRule(
                        description="Expire untagged images after 1 day",
                        tag_status=ecr.TagStatus.UNTAGGED,
                        max_image_age=cdk.Duration.days(1),
                    )
                ]
            )

            self.repositories[cfg.repository_name] = repo

            # Outputs for build pipelines
            cdk.CfnOutput(
                self,
                f"{logical_prefix}RepositoryUri",
                value=repo.repository_uri,
                description=f"URI for {cfg.repository_name}",
                export_name=f"{self.stack_name}-{logical_prefix}RepositoryUri",
            )

        self.repository = self.repositories["chef-agent"]

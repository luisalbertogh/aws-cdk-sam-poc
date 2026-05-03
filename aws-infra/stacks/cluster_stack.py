"""
ClusterStack — deploys the ECS cluster for the Chef UI.

Design decisions
----------------
- Separate stack: ensures the cluster exists before dependent resources like
  SecretsStack and EcsStack are created, establishing proper resource ordering.
- Single-purpose: contains only the ECS cluster definition, making it reusable
  across multiple services if needed in the future.
"""

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs
from constructs import Construct


class ClusterStack(cdk.Stack):
    """CDK stack that provisions the ECS cluster for Chef UI."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.IVpc,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -------------------------------------------------------------------
        # ECS cluster
        # -------------------------------------------------------------------
        self.cluster = ecs.Cluster(
            self,
            "ChefUiCluster",
            cluster_name="chef-assistant-cluster",
            vpc=vpc,
        )

        # -------------------------------------------------------------------
        # Outputs
        # -------------------------------------------------------------------
        cdk.CfnOutput(
            self,
            "ClusterName",
            value=self.cluster.cluster_name,
            description="Name of the Chef UI ECS cluster",
            export_name=f"{self.stack_name}-ClusterName",
        )

        cdk.CfnOutput(
            self,
            "ClusterArn",
            value=self.cluster.cluster_arn,
            description="ARN of the Chef UI ECS cluster",
            export_name=f"{self.stack_name}-ClusterArn",
        )

"""
ClusterStack — deploys the ECS cluster and task execution role for the Chef UI.

Design decisions
----------------
- Separate stack: ensures the cluster and execution role exist before dependent
  resources like SecretsStack and EcsStack are created, establishing proper
  resource ordering.
- Task execution role: created with AmazonECSTaskExecutionRolePolicy managed
  policy, granting permissions to pull images from ECR and write logs to
  CloudWatch. This role is used by the ECS agent, not the application container.
- Single-purpose: contains only cluster-level infrastructure that can be shared
  across multiple services if needed in the future.
"""

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_iam as iam
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
        # ECS Task Execution Role
        #
        # This role is assumed by the ECS agent to pull container images from
        # ECR, write logs to CloudWatch, and read secrets from Secrets Manager.
        # It's cluster-level infrastructure shared by all services.
        # -------------------------------------------------------------------
        self.execution_role = iam.Role(
            self,
            "EcsTaskExecutionRole",
            role_name="chef-ui-ecs-task-execution-role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="ECS task execution role for pulling images and writing logs",
            managed_policies=[
                # AWS managed policy that grants ECR pull and CloudWatch Logs write
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )

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
            "ExecutionRoleArn",
            value=self.execution_role.role_arn,
            description="ARN of the ECS task execution role",
            export_name=f"{self.stack_name}-ExecutionRoleArn",
        )

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
